from concurrent.futures import ThreadPoolExecutor
from typing import List

from django.core.management import BaseCommand

from core.apps.base.models import Inventario
from core.apps.base.resources.api_calls import find_cums
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.medicar import obtener_inventario
from core.settings import logger as log


class Command(BaseCommand):
    help = 'Actualiza el inventario'

    def add_arguments(self, parser):
        """
        This allow to send params in the call.
        Ex.:
            python manage.py inventory 920 110 676
        """
        parser.add_argument("centros", nargs="+", type=str)

    def get_all_inventory(self, centro):
        inv = []
        inv = obtener_inventario(centro)
        if inv:
            self.fetch_cums(inv)
        return inv

    @logtime('')
    def delete_inventario(self, centro):
        log.info(f"Eliminando inventario existente {centro}.")
        all_inv_default = Inventario.objects.using('default').filter(centro=centro).all()
        all_inv_server = Inventario.objects.using('server').filter(centro=centro).all()
        if all_inv_default and all_inv_server:
            all_inv_default.delete()
            all_inv_server.delete()

    @logtime('')
    def register_inventario(self, objs):
        log.info(f"Registrando nuevo inventario {objs[0].centro}.")
        Inventario.objects.bulk_create(objs)
        Inventario.objects.using('server').bulk_create(objs)

    def fetch_cums(self, inv: List) -> List:
        """
        A partir de la lista de codigos de barra de articulos
        procedentes de la API, le agrega el cum el cual es buscado
        en otra base de datos a través del 'CodBarra'
        :param inv: Lista de articulos.
        :return: Lista de articulos + la llave 'cum' en cada uno de ellos.
        """
        barras = [item['CodBarra'] for item in inv]
        cums = find_cums(tuple(barras))
        if cums:
            for art in inv:
                art['cum'] = ''
                art['cum'] = cums.get(art['CodBarra'], '')
        else:
            log.warning('No fue posible cargar los cums porque el '
                        'inventario capturado está vacío')

    def process_inventario(self, inv):
        log.info(f"{' Procesando centro # {}.':.>70}".format(inv))
        inventory = self.get_all_inventory(inv)
        if inventory:
            objs_to_create = [Inventario(centro=art['Centro'], cod_mol=art['CodMol'],
                                         cod_barra=art['CodBarra'], cum=art['cum'],
                                         descripcion=art['Descripcion'], lote=art['Lote'],
                                         fecha_vencimiento=art['FechaVencimiento'],
                                         inventario=art['Inventario'],
                                         costo_promedio=art['CostoPromedio'],
                                         cantidad_empaque=art['CantidadEmpaque'])
                              for art in inventory]
            self.delete_inventario(inv)
            self.register_inventario(objs_to_create)
        else:
            log.warning(f"{' Inventario {} vacío al ser consultado en la API ':x^70}".format(inv))

    def handle(self, *args, **options):
        """
        Consulta el inventario en la API de medicar, caso hayan resultados
        son eliminados los registros de inventario de la base de datos
        y posteriormente insertados los nuevos capturados de la API.
        :param args:
        :param options: Dicionario con informacion donde se encuentra la llave 'centros'
                        que tiene una lista con los parámetros recibidos.
                        Ej.: ['920', '880']
        """
        log.info(f"{' INICIANDO ACTUALIZACIÓN DE INVENTARIO ':▼^50}")
        with ThreadPoolExecutor(max_workers=4) as executor:
            [executor.submit(self.process_inventario, inv) for inv in options.get('centros')]
        log.info(f"{' FINALIZANDO ACTUALIZACIÓN DE INVENTARIO ':▲^50}")
