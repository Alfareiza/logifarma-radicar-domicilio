import concurrent
from concurrent.futures import ThreadPoolExecutor
from itertools import groupby, chain
from typing import List

from django.core.management import BaseCommand

from core.apps.base.models import Inventario
from core.apps.base.resources.api_calls import find_cums
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.medicar import obtener_inventario
from core.apps.base.resources.tools import dt_str_to_date_obj
from core.settings import logger as log


class Command(BaseCommand):
    help = 'Actualiza el inventario con base en API externa.'

    def __init__(self):
        super().__init__()
        self.centros = {}

    def add_arguments(self, parser):
        """
        This allow to send params in the call.
        Ex.:
            python manage.py inventory 920 110 676
        """
        parser.add_argument("centros", nargs="+", type=str)

    def update_inventario(self, objs: List[Inventario]) -> None:
        """
        Excluye el inventario de determinado centro y enseguida agrega la lista
        de objetos de Inventario a la base de dados.
        Esto lo hace en grupos, siendo cada uno un centro.
        :param objs: Inventario a ser actualizado.
        """
        for cod_centro, inventario in groupby(objs, key=lambda obj: obj.centro):
            # key = '920', list(inventario) = [<Inventario: 1>, <Inventario: 1>]
            try:
                self.delete_inventario(cod_centro)
            except Exception as e:
                log.error(f"Error al excluir inventario existente de centro {cod_centro}. Error={e}")
            else:
                self.register_inventario(cod_centro, (list(inventario)))
                self.centros.remove(cod_centro)

        if self.centros:
            log.info(f'No hubo inventerio en : {self.centros}')
            for cod_centro in self.centros:
                self.delete_inventario(cod_centro)

    @logtime('INV')
    def delete_inventario(self, centro: str) -> None:
        """
        Excluye el Inventario de determinado centro.
        :param centro: Codigo del centro a ser excluido. Ej.: '404'
        """
        all_inv_default = Inventario.objects.using('default').filter(centro=centro).all()
        # all_inv_server = Inventario.objects.using('server').filter(centro=centro).all()
        if all_inv_default:
            # and all_inv_server):
            all_inv_default.delete()
            # all_inv_server.delete()

    @logtime('INV')
    def register_inventario(self, centro: str, objs: List[Inventario]) -> None:
        """
        Registra masivamente lista de Inventario en base de datos.
        El campo centro es recibido pero no es utilizado en la función
        sino en el decorator.
        :param centro: Codigo del centro a ser agregado. Ej.: '404'
        :param objs: Inventario a ser agregado.
        """
        Inventario.objects.bulk_create(objs)
        # Inventario.objects.using('server').bulk_create(objs)

    @logtime('')
    def fetch_cums(self, total_inv: List[List[dict]]) -> List:
        """
        A partir de la lista de codigos de barra de articulos
        procedentes de la API, le agrega el cum el cual es buscado
        en otra base de datos a través del 'CodBarra'
        :param total_inv: Lista de centros, que a su vez tiene la lista articulos.
        :return: Lista de articulos + la llave 'cum' en cada uno de ellos.
        """
        # Crea una lista con los codigos de barra a partir de la lista de listas
        # logrando 'achatar' total_inv.
        try:
            barras = [art['CodBarra'] for art in list(chain.from_iterable(total_inv))]
        except TypeError:
            print(list(chain.from_iterable(total_inv)))
        cums = find_cums(tuple(barras))
        if cums:
            for centro in total_inv:
                for art in centro:
                    art['cum'] = ''
                    art['cum'] = cums.get(art['CodBarra'], '')
        else:
            log.warning('No fue posible cargar los cums porque el '
                        'inventario capturado está vacío')

    def create_objs(self, total_inv: List[List[dict]]) -> List:
        """
        Crea una lista general con todos los articulos
        siendo cada uno de ellos un modelo Inventario.
        :param total_inv: Lista de centros, que a su vez tiene la lista articulos.
        :return: Lista de modelos de tipo Inventario.
        """
        return [Inventario(centro=art['Centro'], cod_mol=art['CodMol'],
                           cod_barra=art['CodBarra'], cum=art['cum'],
                           descripcion=art['Descripcion'], lote=art['Lote'],
                           fecha_vencimiento=dt_str_to_date_obj(art['FechaVencimiento']),
                           inventario=art['Inventario'],
                           costo_promedio=art['CostoPromedio'],
                           cantidad_empaque=art['CantidadEmpaque'])
                for inv in total_inv for art in inv]

    def handle(self, *args, **options):
        """
        Consulta el inventario en la API de medicar, caso hayan resultados
        son eliminados los registros de inventario de la base de datos
        y posteriormente insertados los nuevos capturados de la API.
        :param args:
        :param options: Diccionario con informacion donde se encuentra la llave 'centros'
                        que tiene una lista con los parámetros recibidos.
                        Ej.: ['920', '880']
        """
        log.info(f"{' INICIANDO ACTUALIZACIÓN DE INVENTARIO ':▼^50}")
        self.centros = set(options.get('centros'))
        total_inventory = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_rad = [executor.submit(obtener_inventario, inv) for inv in options.get('centros')]
            for future in concurrent.futures.as_completed(future_to_rad):
                total_inventory.append(future.result())

        if total_inventory:
            self.fetch_cums(total_inventory)
            objs = self.create_objs(total_inventory)
            self.update_inventario(objs)

        log.info(f"{' FINALIZANDO ACTUALIZACIÓN DE INVENTARIO ':▲^50}")
