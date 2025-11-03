# DaTe Website 2.0

Django and python3.x based website for [Datateknologerna vid Åbo Akademi rf](https://date.abo.fi)

## Requirements

This project requires [Docker](https://www.docker.com) and [Docker Compose](https://docs.docker.com/compose/)

A local `django-admin` is required for translations

## Setup development environment

### 1. Clone this repo

Development happens mainly in the `develop`-branch

### 2. Create env variables

For development, copy the defaults and adjust them to your needs:

```bash
cp .env.example .env
```

If you plan to run a production-like setup, create a dedicated file (for example `.env.prod`) based on `.env.example` and adjust it separately, keeping secrets out of version control.

Edit the files you just created to match your setup.

### 3. Read env variables

**This must be done every time you start your terminal or edit the profile file!**

In the terminal, navigate to the root of the project, where the `env.sh` script is located.

For the development configuration run (this falls back to `.env` and then `.env.example`):

```bash
source env.sh dev
```

To use your production configuration run:

```bash
source env.sh prod
```

You can also load a specific file by passing its relative or absolute path (e.g. `source env.sh path/to/custom.env`).

Now you can run all `date-` commands!

### 4. Start server and setup database and superuser

Start the server with 

```bash
date-start
```

and make sure everything starts ok.

If the `date-start` command complains about docker not being found, make sure that your user account is in the `docker` group (with command `groups $USER`). If it is not, run `usermod -aG docker $USER`, and restart your bash session!

If you want a clean database you can run the 
`date-migrate`
command after everything has started correctly. Otherwise continue on to the next step.

### 5. Set up initial test data

**This will completely delete and recreate the database (all existing data will be lost)**

If you want initial development data run the script `clean-init.sh` in the folder `scripts/`.

If you get an `illegal option error` in your shell, use `/bin/bash clean-init.sh` to run the script instead.

After this you can re-run the date-createsuperuser.

### 6. Try out the server

Visit http://localhost:8000 or whatever your port is.

The admin page is at http://localhost:8000/admin

## Internationalization

NOTE: No need to implement yet

Locales (stupidly called language codes) used in this project

- sv (default)
- fi

The actual language code will be one of

- sv
- fi

### Translations

As the the default language is `sv`, 
we only need to create translations in the language `fi`.

To generate the translation file, called `django.po`
is done by executing the following command **in the root directory of the project**

```bash
$ django-admin makemessages -l fi
```

This creates/updates the `django.po` 
in `date-website/locale/fi/LC_MESSAGES`.

Add translations to the empty fields or use a third party translation software,
such as `Poedit`.

To compile the translations to `django.mo`, use the following command

```bash
$ django-admin compilemessages
```

## Updating the database

### Warning

##### Only use the script for major version upgrades
For minor version upgrades change the `DATE_POSTGRESQL_VERSION` environment variable.

This script will wipe out __ALL__ data from the volume \
MAKE SURE YOU HAVE PROPER BACKUPS BEFORE ATTEMPTING THIS

If the dump command fails all data may be lost.

### How to upgrade major version

Run

#### Make sure `DATE_POSTGRESQL_VERSION` is set to the CURRENT version before running the following command

```bash
./update-postgres.sh target_version [env_file]
```
after which you have to update your environment variables using
Run `source env.sh dev` afterwards to reload your development configuration.
