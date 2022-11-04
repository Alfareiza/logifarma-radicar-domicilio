from datetime import datetime

from django import forms

from core.apps.base.resources.api_calls import api1 as call_api_eps

from core.apps.base.resources.api_calls import api1 as call_api_2


class Home(forms.Form):
    ...


class Instrucciones(forms.Form):
    ...


class AutorizacionServicio(forms.Form):
    num_autorizacion = forms.IntegerField()

    def clean_num_autorizacion(self):
        # PRIMERA API

        resp_api1 = call_api_eps(self.cleaned_data.get('num_autorizacion'))

        # resp_api1 = {"codigo": "1", "mensaje": "Datos no encontrados!2"}
        # resp_api1 = {"ESTADO_AFILIADO": "ACTIVO", "ESTADO_AUTORIZACION": "PROCESADA"}

        if resp_api1.get('codigo') == "1":
            raise forms.ValidationError("Número de autorización no encontrado")

        # Validaciones
        if resp_api1.get('ESTADO_AFILIADO') != 'ACTIVO':
            raise forms.ValidationError("Afiliado no se encuentra activo")

        if resp_api1.get('ESTADO_AUTORIZACION') != 'PROCESADA':
            raise forms.ValidationError("El estado de la autorización no está activa.")

        # if (datetime.now() - resp_api1.get('FECHA_AUTORIZACION')).days > 30:
        #     raise forms.ValidationError("Esta autorización se encuentra vencida.")

        # SEGUNDA API
        # resp_api1 = {"error": "No se han encontrado registros."}


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
