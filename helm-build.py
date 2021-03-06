#!/usr/bin/env python


import sys
from keeval.keeval import S3ConfigStore
import os
import jinja2
import fnmatch
import base64
import argparse
import collections
import pprint
import datetime
import json
import yaml


class ConfigGenerator(object):
    """ Generates a dictionary of file system objects and their parents based off a
    given list of keys.

    Uses keeval to fetch keys from s3.

    Conflicts will be taken from left to right, the rightmost (last) config winning.

    # >>> p = ConfigGenerator('./config1', './config2')
    # >>> data = p.generate()

    """

    def __init__(self, aws_profile, keeval_bucket, *paths):
        # type: (object, object, object) -> object
        self.paths = paths
        # Create the s3 configstore instance from keeval.
        self.store = S3ConfigStore(aws_profile, keeval_bucket)

    @property
    def _delimiter(self):
        return '.'

    def generate(self):
        configs = [self.generate_config(path) for path in self.paths]
        return self.merge_configs(*configs)

    def merge_configs(self, *configs):
        result = {}
        for config in configs:
            self.dict_merge(result, config)
        return result

    def generate_config(self, path):
        path = path + '/'
        nested_dict = {}
        key_list = self.store.list(path)
        key_data = self.store.read_bulk(key_list)
        for key in key_data.keys():
            path_delim = path.replace('/', self._delimiter)
            new_key = key.split(path_delim)[1]
            value = key_data[key].strip()
            if value.isdigit():
                value = int(value)
            new_dict = reduce(lambda res, cur: {cur: res}, reversed(new_key.split(self._delimiter)), value)
            self.dict_merge(nested_dict, new_dict)
        return nested_dict

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


class j2Builder(object):
    def __init__(self, keeval_bucket):
        self.name = 'j2Builder'
        self.keeval_bucket = keeval_bucket

    def base64encode(self, input):
        return base64.b64encode(input)

    def render(self, tpl_path, context):
        sys.stdout.write("Rendering template: " + tpl_path + '\n')
        path, filename = os.path.split(tpl_path)
        j2env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(path),
            undefined=jinja2.StrictUndefined
        )
        j2env.filters['base64encode'] = self.base64encode
        return j2env.get_template(filename).render(context)

    def write_template(self, template_filename, rendered_template):
        # Remove the j2 extension.
        helm_generated_file = os.path.splitext(template_filename)[0]
        #Values files must be written as values.yaml
        if 'values.yaml' not in helm_generated_file:
            helm_generated_file = os.path.splitext(helm_generated_file)[0] + '.generated.yaml'
        else:
            helm_generated_file = os.path.splitext(helm_generated_file)[0] + '.yaml'
        f = open(helm_generated_file, 'w')
        f.write(rendered_template)
        f.close()

# Argument parsing
parser = argparse.ArgumentParser()
parser.add_argument('--bucket', help='s3 Bucket Name', nargs=1, required=True)
parser.add_argument('--deployment', help='deployment name', nargs=1, required=True)
parser.add_argument('--environment', help='project environment', nargs=1, required=True)
parser.add_argument('--image', help='image name', nargs=1, required=False)
parser.add_argument('--imagetag', help='image tag', nargs=1, required=False)
parser.add_argument("--verbose", help="increase output verbosity", action="store_true")


args = parser.parse_args()
keeval_environment = args.environment[0]
keeval_bucket = args.bucket[0]
deployment = args.deployment[0]

if args.verbose:
    sys.stderr.write("Debug on.\n")
    VERBOSE = True
else:
    VERBOSE = False

config_path = keeval_environment


builder = j2Builder(keeval_bucket=keeval_bucket)

# Look for AWS_PROFILE
if 'AWS_PROFILE' in os.environ:
    aws_profile = os.environ['AWS_PROFILE']
else:
    aws_profile = None


sys.stdout.write("Building config for deployment: " + deployment + "\n")

data = {}

#Check for services.json.
services_path = os.path.join('deployments/', deployment + ".json")
sys.stdout.write("Looking for deployment services.json file: " + services_path + "\n")
# Process services key.

if os.path.isfile(services_path):
    with open(services_path) as f_in:
        services_data = json.load(f_in)
    if VERBOSE is True:
        pprint.pprint(services_data)
else:
    sys.stderr.write("Could not find deployment file: " + services_path + "\n")

#Build the dictionary.
generator = ConfigGenerator(
    aws_profile,
    keeval_bucket,
    config_path + '/common',
    config_path + '/deployment/' + deployment,
    config_path + '/provisioning'

)
data = generator.generate()

# Add the services information to the dict. Here because of compatibility with s3 services file.
data['services'] = services_data['services']

# Add some metadata to the dict.
data['deployment'] = deployment
data['environment'] = keeval_environment
data['generatedtime'] = datetime.datetime.utcnow()

if args.image is not None:
    data['image'] = args.image[0]
if args.imagetag is not None:
    data['imagetag'] = args.imagetag[0]

# Loop through templates and render.
if VERBOSE is True:
    pprint.pprint(data)

# Get the j2 files in the current directory.
cwd = os.getcwd()
all_discovered_templates = []

for root, dirnames, filenames in os.walk('.','secrets'):
    for filename in fnmatch.filter(filenames, '*.j2'):
        all_discovered_templates.append(os.path.join(root, filename))

if all_discovered_templates.__len__() is 0:
    sys.stderr.write("Could not find .j2 files. Nothing to do.\n")
    sys.exit(1)

sys.stdout.write("Found templates:\n" + '\n'.join(all_discovered_templates) + '\n\n')

for template in all_discovered_templates:
    rendered_template = builder.render(template, data)
    builder.write_template(template,rendered_template)


