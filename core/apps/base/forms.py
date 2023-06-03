from django import forms

from core.apps.base.models import Barrio, Municipio, Radicacion
from core.apps.base.resources.api_calls import call_api_eps, call_api_medicar
from core.apps.base.resources.tools import read_json
from core.apps.base.validators import validate_aut_exists, validate_med_controlados, validate_status, validate_status_afiliado, \
    validate_status_aut, validate_structure
from core.settings import logger


class Home(forms.Form):
    """
    Vista 1: Página inicial de la aplicación
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
    num_autorizacion = forms.IntegerField(min_value=100_000, )

    def clean_num_autorizacion(self):
        num_aut = self.cleaned_data.get('num_autorizacion')

        # ====== # Validaciones API EPS ======
        if num_aut == 99_999_999:
            resp_eps = read_json('resources/fake.json')
        elif num_aut == 99_999_998:
            resp_eps = read_json('resources/fake_file.json')
        elif rad := Radicacion.objects.filter(numero_radicado=num_aut).first():
            # Consulta para verificar si tiene ssc (acta)
            resp_mcar = call_api_medicar(num_aut)
            validate_status(resp_mcar, rad)
        else:
            resp_eps = call_api_eps(num_aut)

        # Validación de numero de autorización encontrado en API de Cajacopi
        validate_aut_exists(resp_eps, num_aut)

        # Validación de estructura de respuesta de API de Cajacopi
        validate_structure(resp_eps, num_aut)

        # Validación de medicamentos controlados
        validate_med_controlados(resp_eps, num_aut)

        # Validación de status de afiliado
        validate_status_afiliado(resp_eps, num_aut)

        # Validación de status de autorización
        validate_status_aut(resp_eps, num_aut)

        # if (datetime.now() - resp_eps.get('FECHA_AUTORIZACION')).days > 30:
        #     raise forms.ValidationError("Esta autorización se encuentra vencida.")

        # ====== # Validaciones API MEDICAR ======
        if num_aut in [99_999_999, 99_999_998]:
            resp_mcar = {"error": "No se han encontrado registros."}
        else:
            resp_mcar = call_api_medicar(num_aut)

        if not resp_mcar:
            logger.info(f"No se pudo obtener información del radicado #{num_aut}.")
            raise forms.ValidationError("Pedimos disculpas, pero no pudimos obtener información\n"
                                        f"con este número de autorización.\n{num_aut}\n"
                                        "Puedes esperar unos minutos e intentar de nuevo\n"
                                        "o comunícarte con nosotros al \n333 033 3124")

        if resp_mcar.get('autorizacion'):
            radicada_en = resp_mcar.get('nombre_centro_factura')[:-5].strip()
            logger.info(f"{num_aut} se encuentra radicado en {radicada_en}.")
            # TODO actualizar número de acta en bd
            raise forms.ValidationError(f"Esta autorización ({num_aut}) se encuentra radicada en "
                                        f"{radicada_en} con el número de acta: {resp_mcar.get('ssc')}\n\n"
                                        f"Para mayor información te puedes comunicar \n"
                                        f"con nosotros al: 333 033 3124")

        resp_eps['NUMERO_AUTORIZACION'] = num_aut
        logger.info(f"{num_aut} Número de autorización pasó las validaciones.")
        return resp_eps


class FotoFormulaMedica(forms.Form):
    """
    Vista 4:
    Página donde el usuário toma una foto o la escoje
    de su celular.
    """
    src = forms.ImageField(label=False)


class EligeMunicipio(forms.ModelForm):
    """
    Vista 6:
    """

    class Meta:
        model = Municipio
        exclude = ['name', 'departamento']

    municipio = forms.ModelChoiceField(queryset=Municipio.objects.all(),
                                       empty_label="Seleccione un municipio",
                                       widget=forms.RadioSelect(
                                           attrs={'class': 'select_opt'}
                                       ),
                                       label=False
                                       )


class DireccionBarrio(forms.Form):
    """
    Vista 7:
    """
    barrio = forms.ChoiceField(widget=forms.RadioSelect(attrs={'class': 'select_opt'}))
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
    whatsapp = forms.IntegerField(required=False)

    def clean(self):
        cel = self.cleaned_data.get('celular')
        whatsapp = self.cleaned_data.get('whatsapp')

        if not cel:
            logger.info("Número de celular no ingresado incorrecto.")
            raise forms.ValidationError("Por favor ingrese un número de celular.")

        if str(cel)[0] != "3" or len(str(cel)) != 10:
            logger.info(f"Número de celular {cel} incorrecto.")
            raise forms.ValidationError(f"Número de celular incorrecto:\n{cel}")

        if whatsapp and (str(whatsapp)[0] != "3" or len(str(whatsapp)) != 10):
            logger.info(f"Número de whatsapp incorrecto -> \'{whatsapp}\'.")
            raise forms.ValidationError(f"Número de whatsapp incorrecto:\n{whatsapp}")

        # return cel


class DigitaCorreo(forms.Form):
    """
    Vista 9:
    """
    email = forms.CharField(required=False, max_length=255)

    def clean(self):
        if email := self.cleaned_data.get('email'):
            email = email.lower()
            emails = email.split(',') if ',' in email else [email]
            if 0 < len(email) < 5:
                logger.error(
                    f"Usuario ingresó {self.cleaned_data.get('email')} pero "
                    f"se procesó {email}")
            return list(map(lambda n: n.strip(), emails))

        return [email]

