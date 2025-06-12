# Git

## General

Development happens mainly in `develop` branch.

Releases have their own branches and the latest release is marked as main repository.

## Features

Major additions to the program are regarded as features.

Features have their own branches and the branches are named accordingly to the following pattern: `feature/<feature name>`

## Commits

Commit messages need to be short and descriptive. If the commit is a fix to an issue, the issue number is included in the beginning, as: 

    Issue-<number>: <commit message>

# Testing

## Unittests

Unittests are done accordingly to Django documentation: [Testing in Django](https://docs.djangoproject.com/en/2.1/topics/testing/)

Running `python manage.py test` automatically uses the `core.settings.test` configuration so that the suite works without external services like Redis or PostgreSQL.

## Other tests

While developing a feature, make sure it works as intended by testing it manually as well. 

Future testing methods may be added to documentation.

# Documentation

It is highly encouraged to write descriptions for classes and for functions that are not immediately obvious to the untrained eye.

Even other, non-Django files should have some sort of documentation, in case they need to be understood in the future.

## Setup

The setup process needs to be simple and therefore needs to have a proper guide. This is done in the `README.md` in the project root.

# Deployment

The project runs in a container and will be deployed to **Boris**, DaTes new server inside the ÅA network.

The only requirement for other platforms is that they can run Docker.
