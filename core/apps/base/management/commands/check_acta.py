import concurrent
import datetime
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand

from core.apps.base.models import Radicacion
from core.apps.base.resources.api_calls import call_api_medicar, should_i_call_auth, call_api_eps
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.tools import notify, day_slash_month_year, pretty_date
from core.settings import logger


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
        if 'ssc' in resp:
            if resp.get('ssc'):
                self.update_acta_entrega(rad, str(resp.get('ssc')))
            else:
                # Nunca debería entrar aquí. Cuando el radicado no tiene # de acta, retorna:
                # { "error": "No se han encontrado registros." }
                logger.alert(f'Radicado #{rad.numero_radicado} no tiene aún número de acta. {rad.datetime}.')
                self.alert.append(rad)
        else:
            logger.warning(f"\'SSC\' no encontrado en respuesta de API de Radicado #{rad.numero_radicado}.")
            logger.info(f"Validando si fue rechazada o el afiliado falleció.")
            try:
                resp_eps = call_api_eps(rad.numero_radicado)
                if 'ESTADO_AUTORIZACION' in resp_eps and resp_eps['ESTADO_AUTORIZACION'] == 'RECHAZADA':
                    self.update_acta_entrega(rad, 'rechazada por cajacopi')
                elif 'ESTADO_AFILIADO' in resp_eps and resp_eps['ESTADO_AFILIADO'] == 'FALLECIDO':
                    self.update_acta_entrega(rad, 'afiliado fallecido')
                else:
                    self.errs.append(rad)
            except Exception as e:
                notify('error-api', f"ERROR EN API - Radicado #{rad.numero_radicado}", f"ERROR : \n{e}")
                self.errs.append(rad)

    def update_acta_entrega(self, rad, new_value):
        logger.info(f"Actualizando radicado #{rad.numero_radicado} de fecha {format(rad.datetime, '%D %T')}.")
        rad.acta_entrega = new_value
        rad.save()
        self.updated.append(rad.numero_radicado)
