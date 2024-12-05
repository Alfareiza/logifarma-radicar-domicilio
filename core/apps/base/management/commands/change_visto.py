from typing import List

from django.core.management import BaseCommand

from core.apps.base.models import Radicacion
from core.settings import logger


class Command(BaseCommand):
    help = 'Cambia el attributo visto a `False` cuand tenga acta de entrega nula y visto sea `True`'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_queryset(self) -> 'QuerySet':
        return Radicacion.objects.only('id', 'visto', 'acta_entrega').filter(
            acta_entrega__isnull=True, visto=True).order_by('datetime')

    def update(self, radicaciones: List[Radicacion]):
        """Actualiza los radicados para establecer el visto igual a True"""
        if radicaciones:
            Radicacion.objects.bulk_update(radicaciones, ['visto'], batch_size=500)
            logger.info(f'{len(radicaciones)} Radicados fueron actualizados para visto igual a True')
        else:
            logger.info('No se encontraron radicados con acta_entrega igual a Null y visto igual a True')

    def handle(self, *args, **options):
        """Función principal que busca los radicados y los actualiza."""
        logger.info("Iniciando script que cambia 'visto' en radicados")
        qs = self.get_queryset()
        to_update = []
        for radicacion in qs:
            radicacion.visto = False
            to_update.append(radicacion)
        self.update(to_update)
        logger.info("Finalizado script que cambia 'visto' en radicados")
