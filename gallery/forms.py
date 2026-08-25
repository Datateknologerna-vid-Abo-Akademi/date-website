import logging

from django import forms

from core.upload_widgets import DirectUploadField

from .models import Album, ImageProcessingError, Photo

logger = logging.getLogger('date')


def create_photo_from_temp(album, uploaded):
    """Copy a direct-uploaded temp photo to its final key and create the row."""
    from core.uploads import finalize_upload

    photo = Photo(album=album)
    image_field = Photo._meta.get_field('image')
    photo.image.name = finalize_upload(
        uploaded['key'],
        photo,
        image_field,
        uploaded['name'],
        expected_size=uploaded['size'],
    )
    photo._skip_compress = True  # noqa: SLF001 - already compressed client-side
    photo.save()


class AlbumUploadForm(forms.Form):
    album = forms.CharField()
    images = DirectUploadField(scope='gallery', multi=True, label="Bilder")


class AlbumAdminForm(forms.ModelForm):
    images = DirectUploadField(scope='gallery-admin', multi=True, label="Ladda upp flera bilder")

    class Meta:
        model = Album
        fields = '__all__'  # noqa: DJ007

    def _save_m2m(self):
        super()._save_m2m()
        self.skipped_images = []
        for uploaded_file in self.cleaned_data.get('images') or []:
            if isinstance(uploaded_file, dict):
                try:
                    create_photo_from_temp(self.instance, uploaded_file)
                except ValueError as exc:
                    logger.warning(str(exc))
                    self.skipped_images.append(uploaded_file['name'])
            else:
                try:
                    Photo.objects.create(album=self.instance, image=uploaded_file)
                except ImageProcessingError as exc:
                    logger.warning(str(exc))
                    self.skipped_images.append(uploaded_file.name)
