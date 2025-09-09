from django import forms

from core.apps.base.models import Barrio, Municipio, Radicacion
from core.apps.base.resources.cajacopi import obtener_datos_identificacion, obtener_datos_autorizacion
from core.apps.base.resources.medicar import obtener_datos_formula
from core.apps.base.resources.tools import read_json
from core.apps.base.validators import (
    validate_aut_exists,
    validate_email,
    validate_empty_response,
    validate_identificacion_exists,
    validate_med_controlados,
    validate_recent_radicado,
    validate_status,
    validate_status_afiliado,
    validate_status_aut,
    validate_structure, validate_numero_celular, direccion_min_length_validator, validate_numeros_bloqueados,
    certify_celular
)
from core.settings import logger


class Home(forms.Form):
    """
    Vista 1: Página inicial de la aplicación
    """
    ...


class AutorizadoONo(forms.Form):
    """
    Vista : Usuario decide si tiene o no autorización
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
        choices=IDENTIFICACIONES, label='Tipo de documento',
        widget=forms.Select(attrs={'class': 'custom-select'})
    )
    identificacion = forms.CharField(
        min_length=6, max_length=20, label='Identificación',
        widget=forms.TextInput(attrs={'class': 'effect-16', 'autofocus': True})
    )

    def clean(self):
        tipo = self.cleaned_data.get('tipo_identificacion')
        value = self.cleaned_data.get('identificacion')
        flag_new_formula = self.data.get('flag_new_formula')
        entidad = {'c': 'cajacopi', 'f': 'fomag', 'm': 'mutualser'}.get(getattr(self, 'source', ''), '')
        resp = {'documento': f"{tipo}{value}"}

        if value == "99999999":
            resp_eps = read_json('resources/fake_sin_autorizacion.json')
        elif entidad:
            resp_eps = obtener_datos_identificacion(entidad, tipo, value)
            validate_identificacion_exists(entidad, resp_eps, f"{tipo}{value}")
            validate_empty_response(resp_eps, resp['documento'], entidad)
            if not flag_new_formula:
                self.extra_validations(entidad, resp_eps, tipo, value)
                validate_recent_radicado(tipo, value, entidad)
        else:
            raise forms.ValidationError(
                message='Entidad no reconocida.',
                params={
                    'modal_type': 'no_entidad',
                    'modal_title': "No ha sido posible detectar la entidad a la cual estás afiliado.",
                    'modal_body': "<a class='tel' style='text-decoration:none' href='/'>Click aqui</a> para radicar tu domicilio.",
                })

        resp |= {
            'AFILIADO': resp_eps['NOMBRE'],
            'NOMBRE': f"{resp_eps['PRIMER_NOMBRE']} {resp_eps['PRIMER_APELLIDO']}",
            'P_NOMBRE': resp_eps['PRIMER_NOMBRE'],
            'TIPO_IDENTIFICACION': tipo,
            'DOCUMENTO_ID': value,
            'CONVENIO': entidad,
        }
        return resp

    def extra_validations(self, entidad, resp_api, tipo, value):
        """Realiza validaciones extra una vez se tenga información de respuesta de api."""
        if entidad == 'cajacopi':
            validate_identificacion_exists(entidad, resp_api, f"{tipo}:{value}")
            validate_status_afiliado(resp_api, 'ESTADO', f"{tipo}:{value}")
        elif entidad in ('fomag', 'mutualser'):
            # Validaciones extra cuando se consulta usuario fomag sin autorización
            ...


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
            logger.info(msg := f"No se pudo obtener información del radicado #{num_aut}.")
            raise forms.ValidationError(
                message=msg,
                params={
                    'modal_type': 'issue_api',
                    'modal_title': f"Pedimos disculpas, pero no pudimos obtener información del número de autorización {num_aut}.",
                    'modal_body': "Puedes esperar unos minutos e intentar de nuevo o comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
                })

        if resp_mcar.get('autorizacion'):
            radicada_en = resp_mcar.get('nombre_centro_factura')[:-5].strip()
            logger.info(f"{num_aut} se encuentra radicado en {radicada_en}.")
            # TODO actualizar número de acta en bd
            raise forms.ValidationError(
                message='Autorizacion radicada.',
                params={
                    'modal_type': 'autorizacion_radicada',
                    'modal_title': f"Esta autorización ({num_aut}) se encuentra radicada en {radicada_en} con el número de acta: {resp_mcar.get('ssc')}.",
                     'modal_body': "Para más información comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
                })

        resp_eps['NUMERO_AUTORIZACION'] = num_aut
        resp_eps['CONVENIO'] = 'cajacopi'
        # logger.info(f"{num_aut} Número de autorización pasó las validaciones.")
        return resp_eps


class Orden(forms.Form):
    no_orden = forms.IntegerField(min_value=100_000, label='Número para facturar',
                                  widget=forms.TextInput(attrs={'class': 'effect-16', 'autofocus': True}))

    def clean(self):
        orden = self.cleaned_data.get('no_orden')
        str_orden = str(orden)
        if not orden or len((str_orden)) < 6:
            raise forms.ValidationError("Por favor ingrese un número para facturar válido.")

        if rad := Radicacion.objects.filter(numero_radicado=str_orden).first():
            # Consulta para verificar si tiene ssc (acta)
            resp_mcar = obtener_datos_formula(orden, '806008394')  # Nit mutual ser
            validate_status(resp_mcar, rad)

        return {'NUMERO_AUTORIZACION': orden}


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
                                           attrs={'class': 'h-5 w-5 text-blue-600 focus:ring-2 focus:ring-blue-400 border-gray-300'}
                                       ),
                                       label=False
                                       )


class DireccionBarrio(forms.Form):
    """
    Vista 5:
    """
    barrio = forms.ChoiceField(widget=forms.RadioSelect(attrs={'class': 'h-5 w-5 text-blue-600 focus:ring-2 focus:ring-blue-400 border-gray-300'}))
    direccion = forms.CharField(min_length=5, max_length=40, validators=[direccion_min_length_validator])

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
    otp_code = forms.CharField(required=False, widget=forms.HiddenInput(), label='OTP Code')
    celular_validado = forms.BooleanField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.wizard = kwargs.pop('wizard', None)
        super().__init__(*args, **kwargs)

    def _get_previous_step_data(self):
        """
        Get previous step data without triggering validation/API calls.
        This method accesses the already validated and stored data from the wizard.
        Returns a dictionary with both authorization data and municipality data.
        """
        if not self.wizard:
            return {}

        result = {
            'autorizacion_data': {},
            'municipio_data': {}
        }

        # Get authorization data from various sources
        autorizacion_data = {}
        
        # First, try to get data from rad_data (set when autorizacionServicio step is processed)
        if hasattr(self.wizard, 'rad_data') and self.wizard.rad_data:
            # rad_data contains the cleaned_data from autorizacionServicio step
            # which includes the API response data with TIPO_IDENTIFICACION and DOCUMENTO_ID
            autorizacion_data = self.wizard.rad_data.get('num_autorizacion', {})

        if not autorizacion_data and (autorizacion_servicio_data := self.wizard.storage.extra_data.get(
            'autorizacion_servicio', {}
        )):
            autorizacion_data = autorizacion_servicio_data.get('num_autorizacion', {})

        if not autorizacion_data and (autorizaciones_data := self.wizard.storage.extra_data.get(
            'autorizaciones', {}
        )):
            autorizacion_data = autorizaciones_data

        # Get municipality data from eligeMunicipio step
        municipio_data = {}
        
        # Try to get eligeMunicipio data from extra_data first
        if elige_municipio_data := self.wizard.storage.extra_data.get('elige_municipio', {}):
            municipio_data = elige_municipio_data
        else:
            # Fallback: try to get raw step data (this might still trigger validation, so use as last resort)
            try:
                elige_municipio_step_data = self.wizard.storage.get_step_data('eligeMunicipio')
                if elige_municipio_step_data:
                    # Extract the municipio data from the step data
                    municipio_data = elige_municipio_step_data
            except Exception:
                pass

        result['autorizacion_data'] = autorizacion_data
        result['municipio_data'] = municipio_data  # ex.: 'Barranquilla, Atlántico'
        
        return result

    def clean(self):
        cleaned_data = super().clean()
        cel = cleaned_data.get('celular')
        whatsapp = cleaned_data.get('whatsapp')
        otp_code = cleaned_data.get('otp_code')

        if not cel:
            raise forms.ValidationError("Por favor ingrese un número de celular.")

        validate_numero_celular(cel)
        validate_numeros_bloqueados(cel)
        if whatsapp:
            validate_numero_celular(whatsapp)

        if otp_code:
            # Si llega aquí es pq el celular ha sido validado en el front
            cleaned_data.update({'celular_validado': True})
        else:
            tipo_documento, documento, municipio_data = '', '', {}
            if self.wizard:
                # Access raw step data without triggering validation/API calls
                previous_data = self._get_previous_step_data()
                autorizacion_data = previous_data.get('autorizacion_data', {})
                municipio_data = previous_data.get('municipio_data', {})
                
                if autorizacion_data and 'DOCUMENTO_ID' in autorizacion_data:
                    tipo_documento = autorizacion_data.get('TIPO_IDENTIFICACION')
                    documento = autorizacion_data.get('DOCUMENTO_ID')
            
            _, municipio_name, _ = municipio_data.split(';')
            certify_celular(cel, tipo_documento, documento, municipio_name)

        return cleaned_data


class DigitaCorreo(forms.Form):
    """
    Vista 7:
    """
    email = forms.CharField(required=True, max_length=255)

    def clean(self):
        email = self.cleaned_data.get('email', '').lower()
        emails = email.split(',') if ',' in email else [email]

        for email in emails:
            validate_email(email.strip())

        if 0 < len(email) < 5:
            logger.error(f"Usuario ingresó {self.cleaned_data.get('email')} "
                         f"pero se procesó {email}")

        return list(map(lambda n: n.strip(), emails))
