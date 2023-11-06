from django import forms
from django.utils.safestring import mark_safe

from core.apps.base.models import Barrio, Municipio, Radicacion
from core.apps.base.resources.cajacopi import obtener_datos_identificacion, obtener_datos_autorizacion
from core.apps.base.resources.medicar import obtener_datos_formula
from core.apps.base.resources.tools import read_json, has_accent
from core.apps.base.validators import (
    validate_aut_exists,
    validate_med_controlados,
    validate_status,
    validate_status_afiliado,
    validate_status_aut,
    validate_structure, validate_identificacion_exists, validate_email
)
from core.settings import logger


class Home(forms.Form):
    """
    Vista 1: Página inicial de la aplicación
    """
    ...


class SinAutorizacion(forms.Form):
    """
    Vista 2 (Flujo sin autorización):
    Página que recibe núnero de cedula y
    verifica en API externas.
    Si la respuesta es positiva, se dirigirá a la
    vista FotoFormulaMedica, sino  responderá con un
    mensaje (modal) de error.
    """
    IDENTIFICACIONES = (
        ("CC", "CC - Cédula de ciudadanía"),  # Cédula de ciudadanía
        ("TI", "TI - Tarjeta de identidad"),  # Tarjeta de identidad
        ("RC", "RC - Registro civil"),  # Registro civil
        ("CN", "CN - Certificado de nacido vivo"),  # Certificado de nacido vivo
        ("CD", "CD - Carné diplomático"),  # Carné diplomático
        ("PA", "PA - Pasaporte"),  # Pasaporte
        ("PE", "PE - Permiso especial de pernamencia"),  # Permiso especial de pernamencia
        ("PT", "PT - Permiso por protección temporal"),  # Permiso por protección temporal
        ("SC", "SC - Salvo conducto"),  # Salvo conducto
        ("CE", "CE - Cedula de extranjería"),  # Cedula de extranjería
        ("MS", "MS - Menor sin ID"),  # Menor sin ID
        ("AS", "AS - Adulto sin ID"),  # Adulto sin ID
    )
    tipo_identificacion = forms.ChoiceField(
        choices=IDENTIFICACIONES, label='Tipo de identificación',
        widget=forms.Select(attrs={'class': 'custom-select'})
    )
    identificacion = forms.CharField(
        min_length=6, max_length=20, label='Identificación',
        widget=forms.TextInput(attrs={'class': 'effect-16'})
    )

    def clean(self):
        tipo = self.cleaned_data.get('tipo_identificacion')
        value = self.cleaned_data.get('identificacion')

        resp = {'documento': f"{tipo}{value}"}

        if value == "99999999":
            resp_eps = read_json('resources/fake_sin_autorizacion.json')
        else:
            resp_eps = obtener_datos_identificacion(tipo, value)

            if not resp_eps:
                logger.info(f"No se pudo obtener información del usuario {resp['documento']}.")
                raise forms.ValidationError(mark_safe("Pedimos disculpas, pero no pudimos obtener información<br>"
                                                      f"con esta identificación: <br>{resp['documento'][:2]} {resp['documento'][2:]}<br><br>"
                                                      "Puedes esperar unos minutos e intentar de nuevo<br>"
                                                      "o comunícarte con nosotros al <br>333 033 3124"))

            validate_identificacion_exists(resp_eps, f"{tipo}:{value}")
            validate_status_afiliado(resp_eps, 'ESTADO', f"{tipo}:{value}")

        resp.update(
            {'AFILIADO': resp_eps['NOMBRE'],
             'NOMBRE': f"{resp_eps['PRIMER_NOMBRE']} {resp_eps['PRIMER_APELLIDO']}",
             'P_NOMBRE': resp_eps['PRIMER_NOMBRE'],
             'TIPO_IDENTIFICACION': tipo,
             'DOCUMENTO_ID': value}
        )
        return resp


class AutorizacionServicio(forms.Form):
    """
    Vista 2:
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
            resp_mcar = obtener_datos_formula(num_aut)
            validate_status(resp_mcar, rad)
        else:
            resp_eps = obtener_datos_autorizacion(num_aut)

        # Validación de numero de autorización encontrado en API de Cajacopi
        validate_aut_exists(resp_eps, num_aut)

        # Validación de estructura de respuesta de API de Cajacopi
        validate_structure(resp_eps, num_aut)

        # Validación de medicamentos controlados
        validate_med_controlados(resp_eps, num_aut)

        # Validación de status de afiliado
        validate_status_afiliado(resp_eps, 'ESTADO_AFILIADO', str(num_aut))

        # Validación de status de autorización
        validate_status_aut(resp_eps, num_aut)

        # if (datetime.now() - resp_eps.get('FECHA_AUTORIZACION')).days > 30:
        #     raise forms.ValidationError("Esta autorización se encuentra vencida.")

        # ====== # Validaciones API MEDICAR ======
        if num_aut in [99_999_999, 99_999_998]:
            resp_mcar = {"error": "No se han encontrado registros."}
        else:
            resp_mcar = obtener_datos_formula(num_aut)

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
    Vista 3 (Opcional):
    Página donde el usuário toma una foto o la escoje
    de su celular.
    """
    src = forms.ImageField(label=False)


class EligeMunicipio(forms.ModelForm):
    """
    Vista 4:
    """

    class Meta:
        model = Municipio
        exclude = ['name', 'departamento']

    municipio = forms.ModelChoiceField(queryset=Municipio.objects.filter(activo=True),
                                       empty_label="Seleccione un municipio",
                                       widget=forms.RadioSelect(
                                           attrs={'class': 'select_opt'}
                                       ),
                                       label=False
                                       )


class DireccionBarrio(forms.Form):
    """
    Vista 5:
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
    Vista 6:
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
    Vista 7:
    """
    email = forms.CharField(required=False, max_length=255)

    def clean(self):
        if email := self.cleaned_data.get('email'):
            email = email.lower()
            emails = email.split(',') if ',' in email else [email]

            for email in emails:
                validate_email(email.strip())

            if 0 < len(email) < 5:
                logger.error(
                    f"Usuario ingresó {self.cleaned_data.get('email')} pero "
                    f"se procesó {email}")

            return list(map(lambda n: n.strip(), emails))

        return [email]
