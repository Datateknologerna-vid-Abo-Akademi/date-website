from django.conf import settings
from django.db import models
from core.storage_backends import PublicMediaStorage

class PublicFileField(models.FileField):
    def __init__(self, verbose_name=None, name=None, upload_to='', storage=None, **kwargs):
        if settings.USE_S3:
            storage = PublicMediaStorage()
        super().__init__(verbose_name, name, upload_to, storage, **kwargs)
