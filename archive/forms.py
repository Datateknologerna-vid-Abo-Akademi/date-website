from django import forms
from .models import Collection, Picture


class PictureUploadForm(forms.Form):
    album = forms.CharField()
    images = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={'multiple': True}))


class CollectionUpdateForm(forms.ModelForm):
    images = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={'multiple': True}))

    class Meta:
        model = Collection
        fields = (
            'title',
            'images'
        )


class PictureAdminForm(forms.ModelForm):
    images = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}),
                             label="Ladda upp flera bilder",
                             required=False)

    class Meta:
        model = Collection
        fields = '__all__'

    def save(self, *args, **kwargs):
        collection = super(PictureAdminForm, self).save(*args, **kwargs)
        if hasattr(self.files, 'getlist'):
            print(self.files.getlist('images'))
            for f in self.files.getlist('images'):
                Picture.objects.create(collection=collection, image=f)
        return collection
