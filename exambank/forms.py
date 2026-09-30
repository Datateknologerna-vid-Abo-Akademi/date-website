import logging

from django import forms
from django.utils.translation import gettext_lazy as _

from core.admin_base import UnfoldFormMixin
from core.upload_widgets import DirectUploadField

from .models import ExamArchive, ExamBankAccessSettings, ExamFile

logger = logging.getLogger('date')


class ExamUploadForm(forms.Form):
    title = forms.CharField()
    exam = DirectUploadField(scope='exambank', multi=True, label="Tentor")


class ExamArchiveUploadForm(forms.Form):
    title = forms.CharField()


class ExamArchiveAdminForm(forms.ModelForm):
    files = DirectUploadField(scope='admin', bucket='private', multi=True, label="Ladda upp flera dokument")  # type: ignore[assignment]

    class Meta:
        model = ExamArchive
        fields = '__all__'  # noqa: DJ007

    def _save_m2m(self):
        super()._save_m2m()
        for uploaded_file in self.cleaned_data.get('files') or []:
            if isinstance(uploaded_file, dict):
                try:
                    create_exam_file_from_temp(self.instance, uploaded_file)
                except ValueError as exc:
                    logger.warning('Skipped exam file %s: %s', uploaded_file.get('name'), exc)
            else:
                ExamFile.objects.create(archive=self.instance, document=uploaded_file, title=uploaded_file)


class ExamBankAccessSettingsAdminForm(UnfoldFormMixin, forms.ModelForm):
    PASSWORD_PLACEHOLDER = '********'  # noqa: S105

    password = forms.CharField(
        label=_('Lösenord'),
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text=_(
            'Används bara när inloggning inte krävs. '
            'Lämna tomt för inget lösenord, eller behåll markeringen för att spara nuvarande lösenord.'
        ),
    )

    class Meta:
        model = ExamBankAccessSettings
        fields = ('require_sign_in',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.has_password:
            self.fields['password'].initial = self.PASSWORD_PLACEHOLDER

    def save(self, commit=True):
        settings = super().save(commit=False)
        password = self.cleaned_data.get('password', '')
        if password != self.PASSWORD_PLACEHOLDER:
            settings.set_password(password)
        if commit:
            settings.save()
            self.save_m2m()
        return settings


class ExamBankPasswordForm(forms.Form):
    password = forms.CharField(
        label=_('Lösenord'),
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, access_settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_settings = access_settings

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.access_settings or not self.access_settings.check_password(password):
            raise forms.ValidationError(_('Fel lösenord.'))
        return password


def create_exam_file_from_temp(archive, uploaded, title=None):
    """Copy a direct-uploaded temp exam file to its final key and create the row.

    The public upload flow passes the form's title; admin bulk uploads default
    to the filename, matching the classic behavior.
    """
    from core.uploads import finalize_upload

    exam_file = ExamFile(archive=archive, title=title or uploaded['name'])
    field = ExamFile._meta.get_field('document')
    exam_file.document.name = finalize_upload(
        uploaded['key'],
        exam_file,
        field,
        uploaded['name'],
        expected_size=uploaded['size'],
    )
    exam_file.save()
