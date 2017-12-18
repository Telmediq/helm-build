# helm-build

# Install by simply git cloning to ~/.helm/plugins

# Run this against the devops-k8s repository.

# You can confirm the installation by:
helm plugin list

# s3

The directory structure is important on s3 since build will produce a nested dictionary for jinja to consume.
### For example:

    config.development.telmediq.com/
    └── development
        ├── common
        │   └── spv2
        │       ├── DJANGO_SETTINGS_MODULE
        │       ├── NEW_RELIC_CONFIG_FILE
        │       ├── NEW_RELIC_ENVIRONMENT
        │       ├── TELMEDIQ_WEB_PORT
        │       ├── rabbitmq
        │       │   ├── FIRST_RUN
        │       │   ├── RABBITMQ_ERLANG_COOKIE
        │       │   └── RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS
        │       └── redis
        │           └── REDIS_PASSWORD
        ├── deployment
        │   ├── dep1
        │   │   └── spv2
        │   │       ├── TELMEDIQ_DATABASE_PASSWORD
        │   │       └── rabbitmq
        │   └── dep2
        │       └── spv2
        │           └── rabbitmq
        ├── infrastructure
        │   └── common
        │       ├── development_database_name
        │       ├── development_database_username
        │       ├── telmediq_database_password
        │       └── userdata
        └── provisioning
            └── spv2
                ├── PROVISIONING_DATABASE_HOST
                ├── PROVISIONING_DATABASE_PASSWORD
                ├── PROVISIONING_DATABASE_PORT
                └── PROVISIONING_DATABASE_USER

Secrets and configuration data will be merged based on last write to the dict. Most specific details should be applied last.

Provisioning config is currently used to provision new deployment environments.

# Usage:

Make sure your current directory is the root of the directory, build with recurse looking for j2 files.


    helm build \
    --bucket config.development.telmediq.com \
    --deployment docker-improvements-redux \
    --environment development \
    --image docker-repo/project \
    --imagetag develop

# Jinja2 Format

Jinja2 format should follow normal conventions where:

    ENVIRONMENT_VARIABLE_NAME: {{ spv2.ENVIRONMENT_VARIABLE_NAME }}