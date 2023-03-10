from django import forms
from django.utils import timezone

from core.apps.base.models import Municipio, Barrio, Radicacion
from core.apps.base.resources.api_calls import call_api_eps, call_api_medicar
from core.apps.base.resources.tools import read_json, pretty_date
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
            dt = pretty_date(rad.datetime.astimezone(timezone.get_current_timezone()))
            logger.info(f"Número de autorización {num_aut} radicado {dt}.")
            raise forms.ValidationError(f"Número de autorización {num_aut} radicado {dt}.\n\n"
                                        f"Si tiene alguna duda se puede comunicar con nosotros al 3330333124.")
        else:
            resp_eps = call_api_eps(num_aut)

        if resp_eps.get('codigo') == "1":
            logger.info(f"Número de autorización {num_aut} no encontrado.")
            raise forms.ValidationError(f"Número de autorización {num_aut} no encontrado\n\n"
                                        "Por favor verifique\n\n"
                                        "Si el número está correcto, comuníquese con cajacopi EPS\n"
                                        "al 01 8000 111 446")
        inconsistencia = False
        if len(list(resp_eps.keys())) == 0 or len(str(num_aut)) > 20:
            inconsistencia = True
        else:
            for k, v in resp_eps.items():
                if k == 'DOCUMENTO_ID' and len(v) > 32:
                    inconsistencia = True
                    break
                if k == 'AFILIADO' and len(v) > 150:
                    inconsistencia = True
                    break
                if k == 'num_aut' and len(v) > 24:
                    inconsistencia = True
                    break

        if inconsistencia:
            logger.info(f"Incosistencia en radicado #{num_aut}.")
            raise forms.ValidationError(f"Detectamos un problema interno con este número de autorización\n"
                                        f"{num_aut}\n\n"
                                        "Comuníquese con Logifarma al 3330333124")

        if resp_eps.get('ESTADO_AFILIADO') != 'ACTIVO':
            logger.info(f"EL estado del afiliado de radicado #{num_aut} no se encuentra activo.")
            raise forms.ValidationError("Afiliado no se encuentra activo.")

        if resp_eps.get('ESTADO_AUTORIZACION') != 'PROCESADA':
            logger.info(f"El estado de la autorización #{num_aut} es diferente de PROCESADA.")
            raise forms.ValidationError("El estado de la autorización no está activa.")

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
            logger.info(f"Número de autorización {num_aut} se encuentra radicado {radicada_en}.")
            raise forms.ValidationError(f"Esta autorización ({num_aut}) se encuentra radicada en "
                                        f"{radicada_en} con el número de acta: {resp_mcar.get('ssc')}\n\n"
                                        f"Para mayor información te puedes comunicar \n"
                                        f"con nosotros al: 333 033 3124")

        resp_eps['NUMERO_AUTORIZACION'] = num_aut
        logger.info(f"Número de autorización {num_aut} pasó las validaciones.")
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
            emails = email.split(',') if ',' in email else [email]
            return list(map(lambda n: n.strip(), emails))
        return [email]

