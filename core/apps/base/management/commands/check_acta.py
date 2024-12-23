import concurrent
import datetime
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

from django.core import mail
from django.core.management.base import BaseCommand
from django.db.models.functions import Length
from django.template.loader import get_template

from core.apps.base.models import Radicacion, Municipio, Barrio
from core.apps.base.resources.api_calls import get_firebase_acta, should_i_call_auth
from core.apps.base.resources.cajacopi import obtener_datos_autorizacion
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.medicar import obtener_datos_formula
from core.apps.base.resources.tools import (
    make_email, notify, day_slash_month_year,
    pretty_date, update_rad_from_fbase)
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
        self.emails = []

    def calc_interval_dates(self, start=4, end=1):
        """Calculates the dates according to an interval of days"""
        tod = datetime.datetime.now()
        start = datetime.timedelta(days=start)
        end = datetime.timedelta(days=end)
        start = (tod - start).replace(hour=0, minute=0, second=0)
        end = (tod - end).replace(hour=23, minute=59, second=59)
        self.start = pretty_date(start)
        self.end = pretty_date(end)
        return start, end

    def get_radicados_med_autorizados(self, start, end):
        """Busca los radicados con acta de entrega vacío y que el valor de su
            numero_radicado sea menor a 15 caracteres."""
        logger.info('Buscando radicados con medicamentos autorizados')
        return Radicacion.objects.annotate(
            text_len=Length('numero_radicado')
        ).filter(
            datetime__lte=end, acta_entrega=None, text_len__lt=15).order_by('datetime')

    def get_radicados_med_no_autorizados(self, start, end) -> List[Radicacion]:
        """Busca los radicados que el valor de su numero_radicado sea
        mayor a 15 caracteres."""
        logger.info('Buscando radicados con medicamentos no autorizados')
        return Radicacion.objects.annotate(
            text_len=Length('numero_radicado')
        ).filter(
            datetime__lte=end, acta_entrega=None, text_len__gt=15).order_by('datetime')

    @logtime('SCRIPT')
    def handle(self, *args, **options):
        start, end = self.calc_interval_dates()

        logger.info('Ejecutando script de chequeo de actas.')
        connection = mail.get_connection()
        connection.open()
        if rads_med_autorizados := self.get_radicados_med_autorizados(start, end):
            self.process_radicados_medicamentos_autorizados(rads_med_autorizados)

        if rads_med_no_autorizados := self.get_radicados_med_no_autorizados(start, end):
            self.process_radicados_medicamentos_no_autorizados(rads_med_no_autorizados)

        self.sort_rads()
        if self.errs:
            notify('check-acta',
                   f"Reporte de radicados sin acta hasta el {format(end, '%d/%m')}",
                   f"Analisis ejecutado el {day_slash_month_year(datetime.datetime.now())}.\n"
                   f"Radicados analizados: \t{len(rads_med_autorizados) + len(rads_med_no_autorizados)}.\n"
                   f"Radicados actualizados: \t{len(self.updated)}. \n" \
                   f"Radicados sin acta o con error al consultarse: {len(self.errs)}."
                   f"\nEl siguiente reporte puede ser visto en https://domicilios.logifarma.com.co/sinacta/"
                   f"\n {' '.join(self.errs)}")

        # Envia mensajes de alerta de cada autorización
        # connection.send_messages(self.emails)
        for em in self.emails:
            logger.info(f"Correo con asunto {em.subject!r} a ser enviado.")
            time.sleep(random.randint(1, 5))
            em.send()

        connection.close()
        # self.stdout.write(self.style.SUCCESS('Successfully closed poll "%s"' % poll_id))

    def process_radicados_medicamentos_autorizados(self, rads):
        logger.info(f"Verificando {len(rads)} número de radicados con medicamentos autorizados.")
        with ThreadPoolExecutor(max_workers=4) as executor:
            should_i_call_auth()
            future_to_rad = {executor.submit(obtener_datos_formula, r.numero_radicado): r for r in rads}
            for future in concurrent.futures.as_completed(future_to_rad):
                rad = future_to_rad[future]
                try:
                    resp = future.result()
                    self.validate(resp, rad)
                except Exception as exc:
                    print(f'{rad!r} generated an exception: {str(exc)}')

    def process_radicados_medicamentos_no_autorizados(self, rads):
        logger.info(f"Verificando {len(rads)} número de actas de radicados con medicamentos no autorizados.")
        for rad in rads:
            self.errs.append(rad)
            # self.add_alert_email(rad,
            #                      {'FECHA_RADICACION': rad.datetime,
            #                       "AFILIADO": rad.paciente_nombre,
            #                       "TIPO_IDENTIFICACION": rad.paciente_cc[:2],
            #                       "DOCUMENTO_ID": rad.paciente_cc[2:]})

    def sort_rads(self):
        self.errs.sort(key=lambda r: r.datetime)
        self.alert.sort(key=lambda r: r.datetime)
        self.make_str(self.errs, self.alert)

    # @staticmethod
    def make_str(self, *args):
        for lst in args:
            for i, rad in enumerate(lst):
                try:
                    if self.is_autorizacion_con_medicamento_autorizado(rad):
                        lst[i] = f"\t• {rad.numero_radicado} radicado el " \
                                 f"{day_slash_month_year(rad.datetime)} y autorizado" \
                                 f" el {rad.paciente_data['FECHA_AUTORIZACION']}.\n"
                    else:
                        lst[i] = f"\t• F{rad.id} radicado el {day_slash_month_year(rad.datetime)}.\n"
                except Exception as exc:
                    logger.error(f"{self.get_numero_autorizacion(rad)} ERROR: {exc}")

    def validate(self, resp, rad):
        """
        Realiza las siguientes validaciones por radicado en el respectivo orden:
            1. Valida en la respuesta de la api de medicar que tenga un ssc.
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
                self.update_radicacion(rad, resp.get('ssc'))
            else:
                # Nunca debería entrar aquí. Cuando el radicado no tiene # de acta, retorna:
                # { "error": "No se han encontrado registros." }
                logger.info(
                    f'{self.get_numero_autorizacion(rad)} Radicado no tiene aún número de acta. {rad.datetime}.')
                self.alert.append(rad)
        else:
            logger.info(f"{self.get_numero_autorizacion(rad)} sin \'SSC\' en API Medicar, "
                        f"validando estados en API Cajacopi.")
            try:
                resp_eps = obtener_datos_autorizacion(rad.numero_radicado)
                if 'ESTADO_AUTORIZACION' in resp_eps and resp_eps['ESTADO_AUTORIZACION'] in ('RECHAZADA',
                                                                                             'ANULADA'):
                    self.update_acta_entrega(rad, f"{resp_eps['ESTADO_AUTORIZACION'].lower()} por cajacopi")
                elif 'ESTADO_AFILIADO' in resp_eps and resp_eps['ESTADO_AFILIADO'] == 'FALLECIDO':
                    self.update_acta_entrega(rad, 'afiliado fallecido')
                else:
                    logger.info(f"{self.get_numero_autorizacion(rad)} Radicado sin acta.")
                    self.errs.append(rad)
                    # self.add_alert_email(rad, resp_eps)
            except Exception as e:
                notify('error-api', f"ERROR EN API - Radicado #{self.get_numero_autorizacion(rad)}", f"ERROR : \n{e}")
                self.errs.append(rad)

    def update_radicacion(self, rad: Radicacion, acta_entrega: int):
        """
        Actualiza el radicado en bases de datos.
            - Caso haya sido entregado (cuando tiene la llave act en firebase), es
              actualizado con base a la información que está firebase.
            - De lo contrario, solamente actualiza el campo acta_entrega.
        """
        logger.info(f"{self.get_numero_autorizacion(rad)} consultando información en Firebase.")
        resp_fbase = get_firebase_acta(acta_entrega)
        if resp_fbase.get('act'):
            try:
                update_rad_from_fbase(rad, resp_fbase)
            except Exception as e:
                logger.error(f"{self.get_numero_autorizacion(rad)} No fue posible guardar, ERROR={e}")
                self.errs.append(rad)
            else:
                self.updated.append(rad)
        else:
            logger.info(f"{self.get_numero_autorizacion(rad)} tiene acta pero aún no tiene "
                        f"información en Firebase.")
            self.update_acta_entrega(rad, str(acta_entrega))
        self.updated.append(self.get_numero_autorizacion(rad))

    def update_acta_entrega(self, rad, new_value):
        """Actualiza el campo acta_entrega del radicado que se recibe."""
        rad.acta_entrega = new_value
        try:
            logger.info(f"{self.get_numero_autorizacion(rad)} Actualizando "
                        f"acta_entrega para \"{new_value}\".")
            rad.save()
        except Exception as e:
            logger.error(f"{self.get_numero_autorizacion(rad)} No fue posible guardar, ERROR={e}")
            self.errs.append(rad)
        else:
            self.updated.append(self.get_numero_autorizacion(rad))

    def add_alert_email(self, rad, info):
        """
        Agrega un objeto EmailMessage a la fila de emails a ser enviados
        usando template autorización_no_radicada.html con información del radicado.
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
            'NUMERO_AUTORIZACION': self.get_numero_autorizacion(rad),
            'municipio': municipio_str,
            'barrio': barr_str,
            'direccion': rad.direccion,
            'celular': rad.cel_uno,
            'whatsapp': rad.cel_dos,
            'email': [rad.email] if rad.email else [],
        }
        htmly = get_template(BASE_DIR / "core/apps/base/templates/notifiers/autorizacion_no_radicada.html")
        html_content = htmly.render(info_email)

        email = make_email(
            f'Autorización: {self.get_numero_autorizacion(rad)} No radicada',
            html_content,
            # to=['alfareiza@gmail.com'],
            to=['logistica@logifarma.co', 'radicacion.domicilios@logifarma.co'],
            bcc=['alfareiza@gmail.com']
        )

        self.emails.append(email)

    def is_autorizacion_con_medicamento_autorizado(self, rad):
        return 'FECHA_AUTORIZACION' in rad.paciente_data or 'DIAGNOSTICO' in rad.paciente_data

    def get_numero_autorizacion(self, rad: Radicacion) -> str:
        if self.is_autorizacion_con_medicamento_autorizado(rad):
            return rad.numero_radicado
        return f"F{rad.id}"
