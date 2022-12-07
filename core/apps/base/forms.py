from decouple import config, Csv
from django import forms

from core.apps.base.models import Municipio, Barrio
from core.apps.base.resources.api_calls import call_api_eps, call_api_medicar
from core.apps.base.resources.tools import read_json


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
        num_aut = self.cleaned_data.get('num_autorizacion')

        # ====== # Validaciones API EPS ======
        if num_aut == 99_999_999:
            resp_eps = read_json('resources/fake.json')
        else:
            resp_eps = call_api_eps(num_aut)

        if resp_eps.get('codigo') == "1":
            raise forms.ValidationError(f"Número de autorización {num_aut} no encontrado\n\n"
                                        "Por favor verifique\n\n"
                                        "Si el número está correcto, comuníquese con cajacopi EPS\n"
                                        "al 01 8000 111 446")

        if resp_eps.get('ESTADO_AFILIADO') != 'ACTIVO':
            raise forms.ValidationError("Afiliado no se encuentra activo")

        if resp_eps.get('ESTADO_AUTORIZACION') != 'PROCESADA':
            raise forms.ValidationError("El estado de la autorización no está activa.")

        # if (datetime.now() - resp_eps.get('FECHA_AUTORIZACION')).days > 30:
        #     raise forms.ValidationError("Esta autorización se encuentra vencida.")

        # ====== # Validaciones API MEDICAR ======
        if num_aut == 99_999_999:
            resp_mcar = {"error": "No se han encontrado registros."}
        else:
            resp_mcar = call_api_medicar(num_aut)

        if resp_mcar.get('autorizacion'):
            raise forms.ValidationError(f"Este domicilio se encuentra radicado en "
                                        f"{resp_mcar.get('nombre_centro_factura')[:-5].strip()}\n"
                                        f"con el número de acta: {resp_mcar.get('ssc')}\n\n"
                                        f"Para mayor información te puedes comunicar \n"
                                        f"con nosotros al: 333 033 3124")

        resp_eps['NUMERO_AUTORIZACION'] = num_aut
        return resp_eps


class FotoFormulaMedica(forms.Form):
    """
    Vista 4:
    Página donde el usuário toma una foto o la escoje
    de su celular.
    """
    src = forms.ImageField(label=False)


class AvisoDireccion(forms.Form):
    """
    Vista 5:
    """
    ...


class EligeMunicipio(forms.ModelForm):
    """
    Vista 6:
    """

    class Meta:
        model = Municipio
        exclude = ['name', 'departamento']

    municipio = forms.ModelChoiceField(queryset=Municipio.objects.all(),
                                       empty_label="Seleccione un municipio",
                                       widget=forms.Select(
                                           attrs={'class': 'select_opt'}
                                       ),
                                       label=False
                                       )


class DireccionBarrio(forms.Form):
    """
    Vista 7:
    """
    barrio = forms.ChoiceField(widget=forms.Select(attrs={'class': 'select_opt'}))
    direccion = forms.CharField(max_length=40)

    def clean_barrio(self):
        barr = self.cleaned_data.get('barrio')
        if barr == 'X':
            raise forms.ValidationError("Escoja un barrio antes de continuar")
        barr_obj = Barrio.objects.get(id=int(barr))
        return barr_obj.name.title()


class DigitaCelular(forms.Form):
    """
    Vista 8:
    """
    celular = forms.IntegerField()

    def clean_celular(self):
        cel = self.cleaned_data.get('celular')
        if str(cel)[0] != "3" or len(str(cel)) != 10:
            raise forms.ValidationError("Número de celular incorrecto")
        return cel


class DigitaCorreo(forms.Form):
    """
    Vista 9:
    """
    email = forms.EmailField(required=False)
