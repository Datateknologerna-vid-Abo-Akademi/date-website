from django import forms

import logging
logger = logging.getLogger('date')

class FlagForm(forms.Form):
    flag = forms.CharField(label='Insert Flag', max_length=100)

    def __init__(self, *args, **kwargs): 
        super(FlagForm, self).__init__(*args, **kwargs)  
        initial = kwargs.get('initial', {})  
        if initial and initial.get('disable_field'):
            self.fields[initial['disable_field']].disabled = True                
        