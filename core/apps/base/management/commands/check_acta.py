import concurrent
import datetime
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand

from core.apps.base.models import Radicacion
from core.apps.base.resources.api_calls import call_api_medicar, should_i_call_auth
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.tools import notify, day_slash_month_year, pretty_date
from core.settings import logger


class Command(BaseCommand):
    help = 'Consulta el acta de los radicados en un intervalo de tiempo'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        errs, updated, alert = [], [], []
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
                        if 'ssc' in resp:
                            if resp.get('ssc'):
                                logger.info(f"Actualizando radicado #{rad.numero_radicado}"
                                            f" de fecha {format(rad.datetime, '%D %T')}")
                                rad.acta_entrega = str(resp.get('ssc'))
                                rad.save()
                                updated.append(rad.numero_radicado)
                            else:
                                logger.alert(f'Radicado #{rad.numero_radicado} no '
                                             f'tiene aún número de acta. {rad.datetime}.')
                                alert.append(f"\t\t#{rad.numero_radicado} radicado el {day_slash_month_year(rad.datetime)} "
                                             f"y autorizado el {rad.paciente_data['FECHA_AUTORIZACION']}.")
                        else:
                            logger.warning(
                                f"\'SSC\' no encontrado en respuesta de API de Radicado #{rad.numero_radicado}.")
                            errs.append(f"#{rad.numero_radicado} radicado el {day_slash_month_year(rad.datetime)} "
                                        f"y autorizado el {rad.paciente_data['FECHA_AUTORIZACION']}.\n")
                    except Exception as exc:
                        print(f'{rad!r} generated an exception: {exc}')

            if alert or errs:
                notify('check-acta',
                       f"Reporte de radicados sin acta hasta el {format(end, '%d/%m')}",
                       f"Analisis ejecutado el {day_slash_month_year(datetime.datetime.now())}.\n\n" \
                       f"Radicados analizados: {len(rads)}.\n\n" \
                       f"Radicados actualizados: {len(updated)}. \n\n" \
                       f"Radicados sin fecha de acta: {len(alert)}.\n{' '.join(alert)}\n\n" \
                       f"Radicados con error al consultarse: {len(errs)}.\n {' '.join(errs)}")
        else:
            logger.info(f"No se encontraron radicados con \'acta_entrega\' vacía desde el inicio"
                        f" de los tiempos, hasta el {format(end, '%D %T')}.")

        # self.stdout.write(self.style.SUCCESS('Successfully closed poll "%s"' % poll_id))
