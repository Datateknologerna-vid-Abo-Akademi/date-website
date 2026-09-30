import logging

from django import forms

from core.upload_widgets import DirectUploadField

from .models import Collection, Document, PublicFile

logger = logging.getLogger('date')


def _uploaded_files(field_value):
    """Normalize cleaned data to a list of (UploadedFile | dict) entries."""
    return field_value or []


class DocumentAdminForm(forms.ModelForm):
    files = DirectUploadField(scope='admin', bucket='private', multi=True, label="Ladda upp flera dokument")  # type: ignore[assignment]

    class Meta:
        model = Collection
        fields = '__all__'  # noqa: DJ007
        exclude = ('hide_for_gulis',)  # noqa: DJ006

    def save(self, *args, **kwargs):
        # The admin flow calls save(commit=False) and persists the row itself,
        # so the explicit save() below is what actually writes the collection;
        # on the direct commit=True path it is a harmless second save.
        collection = super().save(*args, **kwargs)
        collection.save()
        for f in _uploaded_files(self.cleaned_data.get('files')):
            if isinstance(f, dict):
                try:
                    create_document_from_temp(collection, f)
                except ValueError as exc:
                    logger.warning('Skipped document %s: %s', f.get('name'), exc)
            else:
                Document.objects.create(collection=collection, document=f, title=f)
        return collection


class PublicAdminForm(forms.ModelForm):
    files = DirectUploadField(scope='admin', bucket='public', multi=True, label="Ladda upp flera filer")  # type: ignore[assignment]

    class Meta:
        model = Collection
        fields = '__all__'  # noqa: DJ007

    def save(self, *args, **kwargs):
        # See DocumentAdminForm.save: the explicit save persists the collection
        # on the admin commit=False path.
        collection = super().save(*args, **kwargs)
        collection.save()
        for f in _uploaded_files(self.cleaned_data.get('files')):
            if isinstance(f, dict):
                try:
                    create_public_file_from_temp(collection, f)
                except ValueError as exc:
                    logger.warning('Skipped public file %s: %s', f.get('name'), exc)
            else:
                PublicFile.objects.create(collection=collection, some_file=f)
        return collection


def create_document_from_temp(collection, uploaded):
    """Copy a direct-uploaded temp document to its final key and create the row."""
    from core.uploads import finalize_upload

    document = Document(collection=collection, title=uploaded['name'])
    field = Document._meta.get_field('document')
    document.document.name = finalize_upload(
        uploaded['key'],
        document,
        field,
        uploaded['name'],
        expected_size=uploaded['size'],
    )
    document.save()


def create_public_file_from_temp(collection, uploaded):
    """Copy a direct-uploaded temp public file to its final key and create the row."""
    from core.uploads import finalize_upload

    public_file = PublicFile(collection=collection)
    field = PublicFile._meta.get_field('some_file')
    public_file.some_file.name = finalize_upload(
        uploaded['key'],
        public_file,
        field,
        uploaded['name'],
        expected_size=uploaded['size'],
    )
    public_file.save()
