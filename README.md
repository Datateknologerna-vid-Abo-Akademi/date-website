# DaTe Website 2.0

Django and python3.x based website for [Datateknologerna vid Åbo Akademi rf](https://date.abo.fi)

## Requirements

This project requires [Docker](https://www.docker.com) and [Docker Compose](https://docs.docker.com/compose/)

A local `django-admin` is required for translations

## Setup development environment

### 1. Clone this repo

Development happens mainly in the `develop`-branch

### 2. Create env variables

Create a copy of `example.profile` and change `example` to your local username.

Eg. `otto.env`

Edit the file you just created to match your setup.

### 3. Read env variables

**This must be done every time you start your terminal or edit the profile file!**

In the terminal, navigate to the root of the project, where your `.env` file is located.

Run the command `source $USER.env`

Now you can run all `date-` commands!

### 4. Start server and setup database and superuser

Start the server with 

```
date-start
```

and make sure everything starts ok.

*TODO: Is migrate needed here?*

In a new window where you remember to run `source $USER.env`, run

```bash
date-migrate
```

After that finishes, run

```bash
date-createsuperuser
```

and create the superuser.

### 5. Try out the server

Visit http://localhost:8000 or whatever your port is.

The admin page is at http://localhost:8000/admin

## Internationalization

Locales (stupidly called language codes) used in this project

- sv_FI (default)
- fi_FI

The actual language code will be one of

- sv-fi
- fi-fi

### Translations

As the the default language is `sv`, 
we only need to create translations in the language `fi`.

To generate the translation file, called `django.po`
is done by executing the following command **in the root directory of the project**

```bash
$ django-admin makemessages -l fi_FI
```

This creates/updates the `django.po` 
in `date-django/locale/fi_FI/LC_MESSAGES`.

Add translations to the empty fields or use a third party translation software,
such as `Poedit`.

To compile the translations to `django.mo`, use the following command

```bash
$ django-admin compilemessages
```

