from django import forms

from .models import Collection, Document, Picture, PublicFile


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class PictureUploadForm(forms.Form):
    album = forms.CharField()
    images = forms.ImageField(required=False, widget=forms.ClearableFileInput())


class ExamUploadForm(forms.Form):
    title = forms.CharField()
    exam = forms.FileField(required=False, widget=forms.ClearableFileInput())


class ExamArchiveUploadForm(forms.Form):
    title = forms.CharField()
    

class PictureAdminForm(forms.ModelForm):
    images = MultipleFileField(label="Ladda upp flera bilder", required=False)

    class Meta:
        model = Collection
        fields = '__all__'

    def save(self, *args, **kwargs):
        collection = super(PictureAdminForm, self).save(*args, **kwargs)
        collection.save()
        if hasattr(self.files, 'getlist'):
            for f in self.files.getlist('images'):
                Picture.objects.create(collection=collection, image=f)
        return collection


class DocumentAdminForm(forms.ModelForm):
    files = forms.FileField(widget=forms.ClearableFileInput(),
                             label="Ladda upp flera dokument",
                             required=False)

    class Meta:
        model = Collection
        fields = '__all__'

    def save(self, *args, **kwargs):
        collection = super(DocumentAdminForm, self).save(*args, **kwargs)
        collection.save()
        if hasattr(self.files, 'getlist'):
            for f in self.files.getlist('files'):
                Document.objects.create(collection=collection, document=f, title=f)
        return collection

class PublicAdminForm(forms.ModelForm):
    files = forms.FileField(widget=forms.ClearableFileInput(),
                             label="Ladda upp flera filer",
                             required=False)

    class Meta:
        model = Collection
        fields = '__all__'

    def save(self, *args, **kwargs):
        collection = super(PublicAdminForm, self).save(*args, **kwargs)
        collection.save()
        if hasattr(self.files, 'getlist'):
            for f in self.files.getlist('files'):
                PublicFile.objects.create(collection=collection, some_file=f)
        return collection
