from django import forms
from django.forms import ModelForm
from .models import Collection, Picture


#  --- FORMS ---
class CollectionForm(ModelForm):
    class Meta:
        model = Collection
        fields = ['title', 'type']


class PictureUploadForm(forms.Form):
        collection_name = forms.CharField(initial='class')
        images = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={'multiple': True}))
