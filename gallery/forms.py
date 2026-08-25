import logging

from django import forms

from core.admin_widgets import SafeAdminMultipleFileWidget

from .models import Album, ImageProcessingError, Photo

logger = logging.getLogger('date')


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)


class AlbumUploadForm(forms.Form):
    album = forms.CharField()
    images = MultipleFileField(required=False)


class AlbumAdminForm(forms.ModelForm):
    images = MultipleFileField(label="Ladda upp flera bilder", required=False, widget=SafeAdminMultipleFileWidget())

    class Meta:
        model = Album
        fields = '__all__'  # noqa: DJ007

    def _save_m2m(self):
        super()._save_m2m()
        self.skipped_images = []
        if hasattr(self.files, 'getlist'):
            for uploaded_file in self.files.getlist('images'):
                try:
                    Photo.objects.create(album=self.instance, image=uploaded_file)
                except ImageProcessingError as exc:
                    logger.warning(str(exc))
                    self.skipped_images.append(uploaded_file.name)
