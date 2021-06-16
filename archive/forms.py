from django import forms

from .models import Collection, Document, Picture, PublicFile


class PictureUploadForm(forms.Form):
    album = forms.CharField()
    images = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={'multiple': True}))


class PictureAdminForm(forms.ModelForm):
    images = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}),
                            label="Ladda upp flera bilder",
                            required=False)

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
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}),
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
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}),
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
