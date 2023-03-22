import concurrent
import datetime
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.template.loader import get_template

from core.apps.base.models import Radicacion, Municipio, Barrio
from core.apps.base.resources.api_calls import call_api_medicar, should_i_call_auth, call_api_eps
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.tools import notify, day_slash_month_year, pretty_date
from core.settings import logger, BASE_DIR


class Command(BaseCommand):
    help = 'Consulta el acta de los radicados en un intervalo de tiempo'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errs = []
        self.updated = []
        self.alert = []
        self.start = None
        self.end = None

    def calc_interval_dates(self, start=4, end=2):
        """Calculates the dates according to an interval of days"""
        tod = datetime.datetime.now()
        s = datetime.timedelta(days=start)
        e = datetime.timedelta(days=end)
        start = (tod - s).replace(hour=0, minute=0, second=0)
        end = (tod - e).replace(hour=23, minute=59, second=59)
        self.start = pretty_date(start)
        self.end = pretty_date(end)
        return start, end

    @logtime('SCRIPT')
    def handle(self, *args, **options):
        _, end = self.calc_interval_dates()
        rads = Radicacion.objects.filter(datetime__lte=end).filter(acta_entrega=None).order_by('datetime')
        logger.info('Ejecutando script de chequeo de actas.')
        if rads:
            logger.info(f"Verificando {len(rads)} número de actas.")
            with ThreadPoolExecutor(max_workers=4) as executor:
                should_i_call_auth()
                future_to_rad = {executor.submit(call_api_medicar, r.numero_radicado): r for r in rads}
                for future in concurrent.futures.as_completed(future_to_rad):
                    rad = future_to_rad[future]
                    try:
                        resp = future.result()
                        self.validate(resp, rad)
                    except Exception as exc:
                        print(f'{rad!r} generated an exception: {exc}')

            self.sort_rads()
            if self.errs:
                notify('check-acta',
                       f"Reporte de radicados sin acta hasta el {format(end, '%d/%m')}",
                       f"Analisis ejecutado el {day_slash_month_year(datetime.datetime.now())}.\n\n" \
                       f"Radicados analizados: {len(rads)}.\n\n" \
                       f"Radicados actualizados: {len(self.updated)}. \n\n" \
                       f"Radicados con error al consultarse: {len(self.errs)}.\n {' '.join(self.errs)}")
        else:
            logger.info(f"No se encontraron radicados con \'acta_entrega\' vacía desde el inicio"
                        f" de los tiempos, hasta el {format(end, '%D %T')}.")

        # self.stdout.write(self.style.SUCCESS('Successfully closed poll "%s"' % poll_id))

    def sort_rads(self):
        self.errs.sort(key=lambda r: r.datetime)
        self.alert.sort(key=lambda r: r.datetime)
        self.make_str(self.errs, self.alert)

    @staticmethod
    def make_str(*args):
        for lst in args:
            for i, rad in enumerate(lst):
                lst[i] = f"\t\t#{rad.numero_radicado} radicado el {day_slash_month_year(rad.datetime)}" \
                         f" y autorizado el {rad.paciente_data['FECHA_AUTORIZACION']}.\n"

    def validate(self, resp, rad):
        """
        Realiza las siguientes validaciones por radicado en el respectivo orden:
            1. Valida en la api de medicar que tenga un ssc.
               De ser así actualiza el campo acta_entrega en la bd.
            2. Si no tiene un ssc, entonces:
                2.1. Valida con la api de cajacopi si el ESTADO_AUTORIZACION es 'RECHAZADA'
                     De ser así actualiza el campo acta_entrega en la bd.
                2.2. Valida con la api de cajacopi si el ESTADO_AFILIADO es 'FALLECIDO'
                     De ser así actualiza el campo acta_entrega en la bd.
                2.3 Sino, entonces es considerado como un radicado que no tiene acta
                    y es agregado a la lista self.errs. Junto a eso también envia un correo
                    con la información de ese radicado.
        :param resp: Respuesta de la api de medicar.
                     (Información previamente capturada de forma asíncrona)
        :param rad: 800102180806
        :return: None
        """
        if 'ssc' in resp:
            if resp.get('ssc'):
                self.update_acta_entrega(rad, str(resp.get('ssc')))
            else:
                # Nunca debería entrar aquí. Cuando el radicado no tiene # de acta, retorna:
                # { "error": "No se han encontrado registros." }
                logger.alert(f'{rad.numero_radicado} Radicado no tiene aún número de acta. {rad.datetime}.')
                self.alert.append(rad)
        else:
            logger.warning(f"{rad.numero_radicado} \'SSC\' no encontrado en API Medicar.")
            logger.info(f"{rad.numero_radicado} Validando si fue rechazada o el afiliado falleció.")
            try:
                resp_eps = call_api_eps(rad.numero_radicado)
                if 'ESTADO_AUTORIZACION' in resp_eps and resp_eps['ESTADO_AUTORIZACION'] == 'RECHAZADA':
                    self.update_acta_entrega(rad, 'rechazada por cajacopi')
                elif 'ESTADO_AFILIADO' in resp_eps and resp_eps['ESTADO_AFILIADO'] == 'FALLECIDO':
                    self.update_acta_entrega(rad, 'afiliado fallecido')
                else:
                    self.errs.append(rad)
                    self.send_alert_mail(rad, resp_eps)
            except Exception as e:
                notify('error-api', f"ERROR EN API - Radicado #{rad.numero_radicado}", f"ERROR : \n{e}")
                self.errs.append(rad)

    def update_acta_entrega(self, rad, new_value):
        logger.info(f"{rad.numero_radicado} Actualizando radicado con fecha {format(rad.datetime, '%D %T')}.")
        rad.acta_entrega = new_value
        rad.save()
        self.updated.append(rad.numero_radicado)

    def send_alert_mail(self, rad, info):
        """
        Envía email usando template autorización_no_radicada.html con información
        del radicado.
        :param rad: Objeto de Radicacion obtenido de la base de datos.
                Ej.: <Radicacion: 829600082168>
        :param info: Información de radicado de api eps.
                     Obs.: No recibe info de api medicar porque esta solo tiene
                           { "error": "No se han encontrado registros."}
                Ej: {
                         'TIPO_IDENTIFICACION': 'CC',
                         'DOCUMENTO_ID': '22728593',
                         'AFILIADO': 'MENDOZA CERVANTES GLORIA ELENA',
                         'P_NOMBRE': 'GLORIA',
                         'S_NOMBRE': 'ELENA',
                         'P_APELLIDO': 'MENDOZA',
                         'S_APELLIDO': 'CERVANTES',
                         'ESTADO_AFILIADO': 'ACTIVO',
                         'SEDE_AFILIADO': 'LURUACO',
                         'REGIMEN': 'CONTRIBUTIVO',
                         'DIRECCION': 'CRA 6 NO 2 41',
                         'CORREO': 'gloriame4ndoza@gmail.com',
                         'TELEFONO': '',
                         'CELULAR': '3002102028',
                         'ESTADO_AUTORIZACION': 'PROCESADA',
                         'FECHA_AUTORIZACION': '20/12/2022',
                         'MEDICO_TRATANTE': 'ERICK CAMPANELLI',
                         'MIPRES': '0',
                         'DIAGNOSTICO': 'D27X-TUMOR BENIGNO DEL OVARIO',
                         'ARCHIVO': '',
                         'IPS_SOLICITA': 'VIVA 1A IPS S.A.',
                         'Observacion': '',
                         'RESPONSABLE_GUARDA': 'VIVA 1A IPS S.A.',
                         'CORREO_RESP_GUARDA': 'mcorrea@viva1a.com.co',
                         'RESPONSABLE_AUT': 'USUARIO API',
                         'CORREO_RESP_AUT': '',
                         'DETALLE_AUTORIZACION': [
                                {'CUMS': '19938908-1',
                                'NOMBRE_PRODUCTO': 'CALCIO 600MG + VITAMINA D  200UI + ISOFLAVONA 25MG TABLETA RECUBIERTA',
                                'CANTIDAD': '30'}
                                ]
                   }

        :return: None
        """
        mun = Municipio.objects.get(id=rad.municipio_id)
        municipio_str = f"{mun.name.title()} - {mun.departamento.title()}"

        barr = Barrio.objects.get(id=rad.barrio_id)
        barr_str = barr.name.title()
        info_email = {
            **info,
            'NUMERO_AUTORIZACION': rad.numero_radicado,
            'municipio':  municipio_str,
            'barrio': barr_str,
            'direccion': rad.direccion,
            'celular': rad.cel_uno,
            'whatsapp': rad.cel_dos,
            'email': [rad.email] if rad.email else [],
        }
        htmly = get_template(BASE_DIR / "core/apps/base/templates/notifiers/autorizacion_no_radicada.html")
        html_content = htmly.render(info_email)
        notify('check-aut',
               f'Autorización: {rad.numero_radicado} No radicada',
               html_content,
               to=['logistica@logifarma.co', 'radicacion.domicilios@logifarma.co'], bcc=['alfareiza@gmail.com']
               )
