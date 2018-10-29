from django import forms


class PictureUploadForm(forms.Form):
        album = forms.CharField()
        images = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={'multiple': True}))
