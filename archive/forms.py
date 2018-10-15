from django import forms

#  --- FORMS ---

class PictureUploadForm(forms.Form):
        album = forms.CharField()
        images = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={'multiple': True}))
