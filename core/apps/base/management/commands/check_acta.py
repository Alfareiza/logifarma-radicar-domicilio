import datetime

from django.core.management.base import BaseCommand

from core.apps.base.models import Radicacion
from core.apps.base.resources.api_calls import call_api_medicar
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.tools import notify
from core.settings import logger


class Command(BaseCommand):
    help = 'Consulta el acta de los radicados en un intervalo de tiempo'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start = None
        self.end = None

    def pretty_date(self, dt) -> str:
        return format(dt, '%d/%h')

    def calc_interval_dates(self, start=1, end=0):
        """Calculates the dates according to an interval of days"""
        tod = datetime.datetime.now()
        s = datetime.timedelta(days=start)
        e = datetime.timedelta(days=end)
        start = (tod - s).replace(hour=0, minute=0, second=0)
        end = (tod - e).replace(hour=23, minute=59, second=59)
        self.start = self.pretty_date(start)
        self.end = self.pretty_date(end)
        return start, end

    @logtime('SCRIPT')
    def handle(self, *args, **options):
        start, end = self.calc_interval_dates()
        rads = Radicacion.objects.filter(datetime__gte=start).filter(datetime__lte=end).filter(
            acta_entrega=None
        )
        errs, updated, alert = [], [], []
        logger.info('Ejecutando script de chequeo de actas.')
        if rads:
            logger.info(f"Verificando {len(rads)} número de actas, desde "
                        f"el {self.start} hasta el {self.end}.")
            for idx, rad in enumerate(rads, 1):
                # Hacer esto asíncronamente para agilizar
                resp = call_api_medicar(rad.numero_radicado)
                if 'ssc' in resp:
                    if resp.get('ssc'):
                        logger.info(
                            f"{idx}. Cambiando acta para radicado #{rad.numero_radicado} de fecha {format(rad.datetime, '%D %T')}")
                        # rad.acta_entrega = str(resp.get('ssc'))
                        # var = rad.save
                        updated.append(rad.numero_radicado)
                    else:
                        logger.alert(
                            f'{idx}.  Radicado #{rad.numero_radicado} no tiene aún número de acta. {rad.datetime}.')
                        alert.append(rad.numero_radicado)
                else:
                    logger.warning(
                        f"{idx}. \'SSC\' no encontrado en respuesta de API de Radicado #{rad.numero_radicado}.")
                    errs.append(rad.numero_radicado)
            notify('check-acta',
                   "PRUEBA",
                   # f"Reporte radicados sin acta del {format(start, '%D')} al {format(end, '%D')}",
                   f"Analisis ejecutado el {format(self.pretty_date(datetime.datetime.now()))}.\n\n" \
                   f"Intervalo analizado: Desde el {self.start} hasta {self.end}.\n\n" \
                   f"Radicados analizados: {len(rads)}.\n\n" \
                   f"Radicados actualizados: {len(updated)}. {', '.join(updated)}\n\n" \
                   f"Radicados sin fecha de acta: {len(alert)}. {', '.join(alert)}\n\n" \
                   f"Radicados con error al consultarse: {len(errs)}. {', '.join(errs)}")
        else:
            logger.info(f"No se encontraron radicados entre el {format(start, '%D %T')} y el {format(end, '%D %T')}.")

        # self.stdout.write(self.style.SUCCESS('Successfully closed poll "%s"' % poll_id))
