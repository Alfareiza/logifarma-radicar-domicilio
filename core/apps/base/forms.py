from django import forms

class AutorizacionPostForm(forms.Form):
    numero_autorizacion = forms.IntegerField(max_length=25)

