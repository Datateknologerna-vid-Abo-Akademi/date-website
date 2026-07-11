from django import forms

from .models import Room


class RoomForm(forms.ModelForm):
    title = forms.CharField()

    class Meta:
        model = Room
        fields = ['name']