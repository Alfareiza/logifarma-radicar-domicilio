from django.core.management import BaseCommand

from core.apps.tasks.utils.main import Dispensacion
from core.settings import logger as log


class Command(BaseCommand):
    help = 'Ejecuta script de dispensación, actualizando las facturas de procesadas activas.'

    def handle(self, *args, **options):
        log.info(f"{' ACTUALIZANDO FACTURAS INICIO ':▼^50}")
        Dispensacion().run()
        log.info(f"{' ACTUALIZANDO FACTURAS INICIO ':▲^50}")
