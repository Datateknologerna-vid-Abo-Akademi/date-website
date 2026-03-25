from django import forms

from .models import ExpenseClaim


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleReceiptField(forms.FileField):
    ALLOWED_TYPES = ('image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf')

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={
            'multiple': True,
            'class': 'form-control',
            'accept': 'image/*,application/pdf',
        }))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not isinstance(data, (list, tuple)):
            data = [data] if data else []
        if not data:
            if self.required:
                raise forms.ValidationError(self.error_messages['required'])
            return []
        files = []
        for f in data:
            f = super().clean(f, initial)
            if f.content_type not in self.ALLOWED_TYPES:
                raise forms.ValidationError('Endast bilder (JPEG, PNG, GIF, WebP) och PDF-filer är tillåtna.')
            files.append(f)
        return files


class ExpenseClaimForm(forms.ModelForm):
    receipts = MultipleReceiptField(required=True, label='Kvitton')

    class Meta:
        model = ExpenseClaim
        fields = ['recipient_name', 'description', 'amount', 'payment_method', 'bank_account']
        labels = {
            'recipient_name': 'Mottagare',
            'description': 'Beskrivning',
            'amount': 'Belopp (EUR)',
            'payment_method': 'Betalningsmetod',
            'bank_account': 'Bankkonto (IBAN)',
        }
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ('payment_method', 'description', 'receipts'):
                continue
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('payment_method') == ExpenseClaim.PAYMENT_BANK:
            if not cleaned_data.get('bank_account'):
                self.add_error('bank_account', 'Bankkontonummer (IBAN) krävs för banköverföring.')
        return cleaned_data
