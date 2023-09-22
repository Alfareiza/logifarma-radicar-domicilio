from typing import List

from django.core.management import BaseCommand

from core.apps.base.models import Inventario
from core.apps.base.resources.api_calls import find_cums
from core.apps.base.resources.medicar import obtener_inventario
from core.settings import logger as log


class Command(BaseCommand):
    help = 'Actualiza el inventario'

    def get_all_inventory(self, centro):
        inv = obtener_inventario(centro)
        self.fetch_cums(inv)
        return inv

    def delete_inventario(self):
        log.info(f"Eliminando inventario existente.")
        all_inv_default = Inventario.objects.using('default').all()
        all_inv_server = Inventario.objects.using('server').all()

        if all_inv_default and all_inv_server:
            all_inv_default.delete()
            all_inv_server.delete()

    def register_inventario(self, objs):
        log.info(f"Registrando nuevo inventario.")
        Inventario.objects.bulk_create(objs)
        Inventario.objects.using('server').bulk_create(objs)

    def fetch_cums(self, inv: List) -> List:
        """
        A partir de la lista de articulos procedentes de la API
        recién consultada, le agrega el cum el cual es buscado
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

    def handle(self, *args, **options):
        """
        Consulta el inventario en la API de medicar, caso hayan resultados
        son eliminados los registros de inventario de la base de datos
        y posteriormente insertados los nuevos capturados de la API.
        :param args:
        :param options:
        :return:
        """
        log.info(f"{' INICIANDO ACTUALIZACIÓN DE INVENTARIO ':▼^50}")
        inventory = self.get_all_inventory(920)
        if inventory:
            objs_to_create = [Inventario(centro=art['Centro'], cod_mol=art['CodMol'],
                                         cod_barra=art['CodBarra'],
                                         cum=art['cum'],
                                         descripcion=art['Descripcion'], lote=art['Lote'],
                                         fecha_vencimiento=art['FechaVencimiento'],
                                         inventario=art['Inventario'],
                                         costo_promedio=art['CostoPromedio'],
                                         cantidad_empaque=art['CantidadEmpaque'])
                              for art in inventory]
            self.delete_inventario()
            self.register_inventario(objs_to_create)
        else:
            log.warning('Inventario vacío al ser consultado en la API.')

        log.info(f"{' FINALIZANDO ACTUALIZACIÓN DE INVENTARIO ':▲^50}")
