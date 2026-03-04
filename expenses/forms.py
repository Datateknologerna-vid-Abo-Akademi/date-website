from django import forms

from .models import ExpenseClaim


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'multiple': True, 'class': 'form-control'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # Django 5 passes a list when allow_multiple_selected=True
        if not isinstance(data, (list, tuple)):
            data = [data] if data else []
        if not data:
            if self.required:
                raise forms.ValidationError(self.error_messages['required'])
            return []
        return [super(MultipleImageField, self).clean(f, initial) for f in data]


class ExpenseClaimForm(forms.ModelForm):
    receipts = MultipleImageField(required=True, label='Receipts')

    class Meta:
        model = ExpenseClaim
        fields = ['recipient_name', 'description', 'amount', 'payment_method', 'bank_account']
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
                self.add_error('bank_account', 'Bank account (IBAN) is required for bank transfer.')
        return cleaned_data
