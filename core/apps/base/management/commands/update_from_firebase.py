import datetime

from django.core.management import BaseCommand

from core.apps.base.models import Radicacion
from core.apps.base.resources.api_calls import get_firebase_acta
from core.apps.base.resources.tools import update_rad_from_fbase
from core.settings import logger


class Command(BaseCommand):
    help = 'Actualiza los radicados con base a la información que está en firebase'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errs = []
        self.updated = []

    def calc_interval_dates(self, start=40, end=10):
        """Calculates the dates according to an interval of days"""
        tod = datetime.datetime.now()
        start = datetime.timedelta(days=start)
        end = datetime.timedelta(days=end)
        start = (tod - start).replace(hour=0, minute=0, second=0)
        end = (tod - end).replace(hour=23, minute=59, second=59)
        return start, end

    def handle(self, *args, **options):
        start, end = self.calc_interval_dates()
        rads = Radicacion.objects.filter(
            datetime__lte=end, datetime__gte=start,
            acta_entrega__isnull=False, estado__isnull=True).order_by('datetime')
        logger.info(f"Actualizando {len(rads)} radicados.")
        for i, rad in enumerate(rads, 1):
            logger.info(f"{i}. {rad.numero_radicado} consultando "
                        f"información en Firebase.")
            if not rad.acta_entrega.isdigit():
                continue
            resp_fbase = get_firebase_acta(int(rad.acta_entrega))
            if resp_fbase.get('act'):
                update_rad_from_fbase(rad, resp_fbase)
                try:
                    rad.save(using='default')
                    # rad.save(using='server')
                except Exception:
                    self.errs.append(rad.numero_radicado)
                else:
                    self.updated.append(rad.numero_radicado)
            else:
                logger.info(f"{i}. {rad.numero_radicado} tiene acta pero "
                            f"aún no tiene información en Firebase.")
                self.errs.append(rad.numero_radicado)
        print(f'Radicados actualizados {len(self.updated)} : {self.updated}')
        print(f'Radicados NO actualizados {len(self.errs)} : {self.errs}')
