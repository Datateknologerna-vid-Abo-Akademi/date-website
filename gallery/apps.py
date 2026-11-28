from django.apps import AppConfig


class GalleryConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'gallery'

    def ready(self):
        import pillow_heif

        pillow_heif.register_heif_opener()
