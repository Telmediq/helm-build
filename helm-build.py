#!/usr/bin/env python

from keeval.keeval import S3ConfigStore
import jinja2
from jinja2 import meta
import os
import sys
import fnmatch
import base64
import argparse


cwd = os.getcwd()
all_discovered_templates = []

import os
import collections
import pprint


class ConfigGenerator(object):
    """ Generates a dictionary of file system objects and their parents based off a
    given list of paths.

    Conflicts will be taken from left to right, the rightmost (last) config winning.

    # >>> p = ConfigGenerator('./config1', './config2')
    # >>> data = p.generate()

    """

    def __init__(self, *paths):
        self.paths = paths

    def generate(self):
        configs = [self.generate_config(path) for path in self.paths]
        return self.merge_configs(*configs)

    def merge_configs(self, *configs):
        result = {}
        for config in configs:
            self.dict_merge(result, config)
        return result

    def generate_config(self, rootdir):
        data = {}

        rootdir = rootdir.rstrip(os.sep) + os.sep
        start = rootdir.rfind(os.sep) + 1

        for path, dirs, files in os.walk(rootdir):

            folders = path[start:].split(os.sep)
            subdir = dict.fromkeys(files)

            for k in subdir.keys():
                subdir[k] = self._get_file_value(os.path.join(path, k))

            parent = reduce(dict.get, folders[:-1], data)
            parent[folders[-1]] = subdir
            pp = pprint.PrettyPrinter()
            pp.pprint(data)
        return data

    def _get_file_value(self, path):
        with open(path) as f:
            value = f.read().strip()
            if value.isdigit():
                value = int(value)
        return value

    @staticmethod
    def dict_merge(dct, merge_dct):
        """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
        updating only top-level keys, dict_merge recurses down into dicts nested
        to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
        ``dct``.
        :param dct: dict onto which the merge is executed
        :param merge_dct: dct merged into dct
        :return: None
        """
        for k, v in merge_dct.iteritems():
            if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.Mapping)):
                ConfigGenerator.dict_merge(dct[k], merge_dct[k])
            else:
                dct[k] = merge_dct[k]




class BuildSecrets(object):
    def __init__(self, keeval_bucket):
        self.name = 'BuildSecrets'
        self.keeval_bucket = keeval_bucket

    def base64encode(self, input):
        return base64.b64encode(input)

    def render(self, tpl_path, context):
        sys.stdout.write("Rendering template: " + tpl_path + '\n')
        path, filename = os.path.split(tpl_path)
        j2env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(path)
        )
        j2env.filters['base64encode'] = self.base64encode
        return j2env.get_template(filename).render(context)


    def get_secret(self, key):
        print "Getting: " + self.keeval_bucket + '/' + key
        kv = S3ConfigStore(profile='development', bucket_name=self.keeval_bucket)
        data = kv.read(key)
        return data

    def write_template(self, template_filename, rendered_template):
        # Remove the j2 extension.
        helm_secret_file = os.path.splitext(template_filename)[0]
        # Remove the yaml extension and add .secrets.
        helm_secret_file = os.path.splitext(helm_secret_file)[0] + '.generated.yaml'
        sys.stdout.write("Writing to: " + helm_secret_file + '\n')
        f = open(helm_secret_file, 'w')
        f.write(rendered_template)
        f.close()

    def dict_from_tree(self, path):
        keydata = dict()
        for dirName, subdirList, fileList in os.walk(path):
            print('Found directory: %s' % dirName)
            keyname = dirName.split(self.keeval_bucket)[1].replace('/','.')
            keyname = keyname.split(keeval_environment)[1].lstrip('.')
            print keyname
            for fname in fileList:
                f = open(dirName + '/' + fname,"r")
                data = f.read()
                keydata[keyname] = data
                print('\t%s' % fname)
        print keydata


# Argument parsing
parser = argparse.ArgumentParser()
parser.add_argument('--bucket', help='s3 Bucket Name', nargs=1, required=True)
parser.add_argument('--deployment', help='deployment name', nargs=1, required=True)
parser.add_argument('--environment', help='project environment', nargs=1, required=True)
parser.add_argument('--image', help='image name', nargs=1, required=True)
parser.add_argument('--imagetag', help='image tag', nargs=1, required=True)

args = parser.parse_args()

keeval_environment = args.environment[0]
keeval_bucket = args.bucket[0]
deployment = args.deployment[0]
image = args.image[0]
image_tag = args.imagetag[0]
bucket_path = '/Users/jrhude/Documents/data/TelmedIQ/t/'
config_path = [bucket_path, keeval_bucket, keeval_environment]
config_path = '/'.join(config_path)

builder = BuildSecrets(keeval_bucket=keeval_bucket)

# Look for AWS_PROFILE
if 'AWS_PROFILE' in os.environ:
    aws_profile = os.environ['AWS_PROFILE']
else:
    aws_profile = None

# Get the j2 files in the current directory.

for root, dirnames, filenames in os.walk('.','secrets'):
    for filename in fnmatch.filter(filenames, '*.j2'):
        all_discovered_templates.append(os.path.join(root, filename))

if all_discovered_templates.__len__() is 0:
    sys.stderr.write("Could not find .j2 files. Nothing to do.\n")
    sys.exit(1)

sys.stdout.write("Found: " + '\n'.join(all_discovered_templates) + '\n')

#Build the dictionary.
generator = ConfigGenerator(
    config_path + '/common',
    config_path + '/deployment/' + deployment,
    config_path + '/provisioning/'
)
data = generator.generate()

# Add some metadata to the dict.
data['deployment'] = deployment
data['environment'] = keeval_environment
data['image'] = image
data['imagetag'] = image_tag

# Loop through templates and render.

for template in all_discovered_templates:
    rendered_template = builder.render(template, data)
    builder.write_template(template,rendered_template)


