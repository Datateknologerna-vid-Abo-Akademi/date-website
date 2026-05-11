from django import forms

from .models import ExamArchive, ExamFile


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


class ExamUploadForm(forms.Form):
    title = forms.CharField()
    exam = MultipleFileField(required=False)


class ExamArchiveUploadForm(forms.Form):
    title = forms.CharField()


class ExamArchiveAdminForm(forms.ModelForm):
    files = MultipleFileField(label="Ladda upp flera dokument", required=False)

    class Meta:
        model = ExamArchive
        fields = '__all__'
        exclude = ('hide_for_gulis',)

    def save(self, *args, **kwargs):
        archive = super().save(*args, **kwargs)
        if hasattr(self.files, 'getlist'):
            for uploaded_file in self.files.getlist('files'):
                ExamFile.objects.create(archive=archive, document=uploaded_file, title=uploaded_file)
        return archive
