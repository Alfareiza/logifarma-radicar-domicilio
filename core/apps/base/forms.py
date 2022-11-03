from django import forms


class Home(forms.Form):
    ...


class Instrucciones(forms.Form):
    ...


class AutorizacionServicio(forms.Form):
    num_autorizacion = forms.IntegerField()


class FotoFormulaMedica(forms.Form):
    ...


class AvisoDireccion(forms.Form):
    ...


class EligeMunicipio(forms.Form):
    ...


class EligeBarrio(forms.Form):
    ...


class DigitaDireccion(forms.Form):
    direccion = forms.CharField(max_length=40)


class DigitaCelular(forms.Form):
    celular = forms.IntegerField()
