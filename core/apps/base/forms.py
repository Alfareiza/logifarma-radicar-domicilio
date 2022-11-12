from datetime import datetime

from decouple import config
from django import forms

from core.apps.base.resources.api_calls import call_api_eps


class Home(forms.Form):
    """
    Vista 1: Página inicial de la aplicación
    """
    ...


class Instrucciones(forms.Form):
    """
    Vista 2: Página que indica los pasos
    """
    ...


class AutorizacionServicio(forms.Form):
    """
    Vista 3:
    Página que recibe autorización de servicio y
    la verifica en 2 APIs externas.
    Si la respuesta es positiva, hará un redirect
    a la vista 4, sino  responderá con un mensaje de
    error.
    """
    num_autorizacion = forms.IntegerField(min_value=100_000)

    def clean_num_autorizacion(self):
        # ====== PRIMERA API ======

        # resp_api1 = call_api_eps(self.cleaned_data.get('num_autorizacion'))

        # resp_api1 = {"codigo": "1", "mensaje": "Datos no encontrados!2"}
        resp_api1 = {"ESTADO_AFILIADO": "ACTIVO", "ESTADO_AUTORIZACION": "PROCESADA",
                     "CORREO": config('EMAIL_TEST'), "AFILIADO": "Lorem Ipsum José"}

        if resp_api1.get('codigo') == "1":
            raise forms.ValidationError("Número de autorización no encontrado")

        # Validaciones
        if resp_api1.get('ESTADO_AFILIADO') != 'ACTIVO':
            raise forms.ValidationError("Afiliado no se encuentra activo")

        if resp_api1.get('ESTADO_AUTORIZACION') != 'PROCESADA':
            raise forms.ValidationError("El estado de la autorización no está activa.")

        # if (datetime.now() - resp_api1.get('FECHA_AUTORIZACION')).days > 30:
        #     raise forms.ValidationError("Esta autorización se encuentra vencida.")
        resp_api1['NUMERO_AUTORIZACION'] = self.cleaned_data.get('num_autorizacion')
        return resp_api1

        # ====== SEGUNDA API ======
        # resp_api1 = {"error": "No se han encontrado registros."}


class FotoFormulaMedica(forms.Form):
    """
    Vista 4:
    Página donde el usuário toma una foto o la escoje
    de su celular.
    """
    # src = forms.ImageField(label='Foto')
    src = forms.CharField(label='Foto')

    def clean_src(self):
        import base64;
        from django.core.files.base import ContentFile
        formato, imgstr = self.cleaned_data.get('src').split(';base64,')
        ext = formato.split('/')[-1]
        return ContentFile(base64.b64decode(imgstr), name=f'formula_medica.{ext}')


class AvisoDireccion(forms.Form):
    """
    Vista 5:
    """
    ...


class EligeMunicipio(forms.Form):
    """
    Vista 6:
    """
    MUNICIPIOS = (
        ("0", "Escoja un municipio"),
        ("1", "Barranquilla, Atlantico"),
        ("2", "Soledad, Atlantico"),
        ("3", "Malambo, Atlantico"),
        ("4", "Baranoa, Atlantico"),
        ("5", "Galapa, Atlantico"),
    )

    municipio = forms.ChoiceField(choices=MUNICIPIOS)

    def clean_municipio(self):
        municipio = self.cleaned_data.get('municipio')
        if municipio == '0':
            raise forms.ValidationError("Escoja un municipio antes de continuar")
        return self.MUNICIPIOS[int(municipio)][1]


class EligeBarrio(forms.Form):
    """
    Vista 7:
    """
    BARRIOS = (
        ("0", "Escoja un barrio"),
        ("1", "El Valle, Atlantico"),
        ("2", "Barrio 2"),
        ("3", "Barrio 3"),
        ("4", "Barrio 4"),
        ("5", "Barrio 5"),
    )

    barrio = forms.ChoiceField(choices=BARRIOS)

    def clean_barrio(self):
        barrio = self.cleaned_data.get('barrio')
        if barrio == '0':
            raise forms.ValidationError("Escoja un barrio antes de continuar")
        return self.BARRIOS[int(barrio)][1]


class DigitaDireccion(forms.Form):
    """
    Vista 8:
    """
    direccion = forms.CharField(max_length=40)


class DigitaCelular(forms.Form):
    """
    Vista 9:
    """
    celular = forms.IntegerField()
    email = forms.EmailField(required=False)
