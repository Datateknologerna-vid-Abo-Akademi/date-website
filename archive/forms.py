from django import forms
import re

from .models import Collection, Document, Picture, PublicFile, slug_transtable, COLLECTION_SLUG_MAX_LENGTH
from date.functions import slugify_max


class SlugCleanMixin:
    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        if slug == "" and "title" in self.cleaned_data:
            base_slug = self.cleaned_data['title'].lower().translate(slug_transtable)
            base_slug = re.sub(r"[^a-zA-Z0-9_]*", '', base_slug)
            base_slug = re.sub(r"__+", '_', base_slug)
            slug = base_slug

            collisions = Collection.objects.filter(slug=slug)
            suffix = 1
            while collisions.exists():
                slug = f"{base_slug}_{suffix}"
                collisions = Collection.objects.filter(slug=slug)
                suffix += 1

        slug = slugify_max(slug, max_length=COLLECTION_SLUG_MAX_LENGTH)
        return slug




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
    images = MultipleFileField(required=False)


class ExamUploadForm(forms.Form):
    title = forms.CharField()
    exam = MultipleFileField(required=False)


class ExamArchiveUploadForm(forms.Form):
    title = forms.CharField()
    

class PictureAdminForm(SlugCleanMixin, forms.ModelForm):
    images = MultipleFileField(label="Ladda upp flera bilder", required=False)
    title = forms.CharField()

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


class DocumentAdminForm(SlugCleanMixin, forms.ModelForm):
    files = MultipleFileField(label="Ladda upp flera dokument", required=False)

    class Meta:
        model = Collection
        fields = '__all__'
        exclude = ('hide_for_gulis',)

    def save(self, *args, **kwargs):
        collection = super(DocumentAdminForm, self).save(*args, **kwargs)
        collection.save()
        if hasattr(self.files, 'getlist'):
            for f in self.files.getlist('files'):
                Document.objects.create(collection=collection, document=f, title=f)
        return collection

class PublicAdminForm(SlugCleanMixin, forms.ModelForm):
    files = MultipleFileField(label="Ladda upp flera filer", required=False)

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
