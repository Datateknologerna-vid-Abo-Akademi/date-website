from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ExamArchive, ExamBankAccessSettings, ExamFile


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
    files = MultipleFileField(label="Ladda upp flera dokument", required=False)  # type: ignore[assignment]

    class Meta:
        model = ExamArchive
        fields = '__all__'  # noqa: DJ007

    def save(self, *args, **kwargs):
        archive = super().save(*args, **kwargs)
        if hasattr(self.files, 'getlist'):
            for uploaded_file in self.files.getlist('files'):
                ExamFile.objects.create(archive=archive, document=uploaded_file, title=uploaded_file)
        return archive


class ExamBankAccessSettingsAdminForm(forms.ModelForm):
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
