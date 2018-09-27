from django import forms

#  --- FORMS ---

class PictureUploadForm(forms.Form):
        collection_name = forms.CharField(initial='class')
        images = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={'multiple': True}))
