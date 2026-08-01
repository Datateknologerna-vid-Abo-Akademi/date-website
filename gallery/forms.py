from django import forms

from .models import Album, Photo


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
    images = MultipleFileField(label="Ladda upp flera bilder", required=False)

    class Meta:
        model = Album
        fields = '__all__'  # noqa: DJ007

    def save(self, *args, **kwargs):
        album = super().save(*args, **kwargs)
        if hasattr(self.files, 'getlist'):
            for uploaded_file in self.files.getlist('images'):
                Photo.objects.create(album=album, image=uploaded_file)
        return album
