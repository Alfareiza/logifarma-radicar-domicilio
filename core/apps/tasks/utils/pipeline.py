import concurrent
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import datetime
from typing import List

from django.db.models import QuerySet

from core.apps.base.resources.api_calls import get_firebase_acta, update_status_factura_cajacopi
from core.apps.base.resources.medicar import obtener_datos_formula
from core.apps.base.resources.tools import notify, day_slash_month_year
from core.apps.tasks.models import FacturasProcesadas
from core.settings import logger as log


@dataclass
class Csv2Dict:
    pk: str = 'Factura'

    def run(self, **kwargs) -> None:
        """Función principal llamada desde core.apps.tasks.utils.main que se encarga de
        procesar el csv y crear un diccionário con los campos 'Factura', 'Fecha Factura',
        'Numero Autorizacion' y 'No SSC'.
        Ej.:
            {
                '19001':
                    {
                    'Factura': '19001',
                    'Fecha Factura': '2023-09-23 09:59:51',
                    'Numero Autorizacion': '774898989',
                    'No SSC': '123456',
                    }
                ...
            }
        Fecha Factura : '2023-09-23 09:59:51'
        :param kwargs: kwargs['csv_reader']: csv.DictReader. Contiene información del csv.
                       kwargs['data']: Dict. Vacío, el cual será rellenado.
        """
        log.info("Comenzando procesamiendo de CSV.")
        for i, row in enumerate(kwargs['csv_reader'], 1):
            key = row[self.pk]
            if row['Convenio'].upper() == 'CAJACOPI' and row['Factura']:
                kwargs['data'][key] = {'Factura': str(row['Factura']),
                                       'Fecha Factura': row['Fecha Factura'],
                                       'Numero Autorizacion': str(row['Numero Autorizacion']),
                                       'No SSC': str(row['No SSC'])}


class DataToDB:

    def run(self, **kwargs):
        """Función principal llamada desde core.apps.tasks.utils.main que se encarga de
        crear los modelos FacturasProcesadas en el dicionario kwargs['data'] y guardarlos
        en la bd."""
        log.info("Creando facturas para guardar en DB.")

        self.create_objs(kwargs['data'])
        facturas_obj = [fac['model'] for _, fac in kwargs['data'].items()]
        self.register_facturas_procesadas(facturas_obj)

        log.info(f"Facturas guardadas en DB!.")

    def register_facturas_procesadas(self, facturas: List[FacturasProcesadas]) -> None:
        """Registra en bd las facturas masivamente, en caso de ya existir, no las rescribe
        y tampoco lanza error."""
        log.info(f"Registrando nuevas facturas.")
        FacturasProcesadas.objects.bulk_create(facturas, ignore_conflicts=True)

    def create_objs(self, data: dict) -> None:
        """
        Altera variable data, agregaándole una llave ('model') a cada diccionaário con
        el Modelo correspondiente.
        :param data: Creado en Csv2Dict, tiene la siguiente estructura:
                    {
                        '19001':
                            {
                            'Factura': '19001',
                            'Fecha Factura': '2023-09-23 09:59:51',
                            'Numero Autorizacion': '774898989',
                            'No SSC': '123456',
         --> Nuevo! -->     'model': <FacturasProcesadas: LGFM-1070556 estado=None>
                            }
                        ...
                    }
        """
        for fac_value, fac_content in data.items():
            fac_content['model'] = FacturasProcesadas(factura=fac_content['Factura'],
                                                      fecha_factura=fac_content['Fecha Factura'],
                                                      numero_autorizacion=fac_content['Numero Autorizacion'],
                                                      acta=fac_content['No SSC'])


@dataclass
class FillExtraDataMedicar:
    errs: list = field(init=False, default_factory=list)

    def get_facturas(self) -> QuerySet:
        """Busca facturas que serán actualizadas."""
        tod = datetime.datetime.now()
        end = (tod - datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59)
        return FacturasProcesadas.objects.filter(fecha_factura__lte=end, valor_total=None).order_by('fecha_factura')

    def run(self, **kwargs):
        """Función principal llamada desde core.apps.tasks.utils.main que se encarga de
        actualizar el campo valor_total del modelo FacturasProcesadas."""
        facturas = self.get_facturas()[:10]
        log.info(f"Iniciando llamados a API medicar para calcular valor_total de {len(facturas)} facturas.")
        self.api_calls(facturas)

    def api_calls(self, facturas: QuerySet[FacturasProcesadas]):
        """
        Llama asíncronamente la función obtener_datos_formula
        para obtener información del numero de autorización y asi
        poder calcular el valor total.
        :param facturas: Facturas buscadas en bd con base lógica implementada en self.get_facturas()
        :return: None.
                Envia un correo en caso de haber problemas con facturas procesadas.
                Ej.:
                    - Medicar no respondió.
        """
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_rad = {executor.submit(obtener_datos_formula, fac.numero_autorizacion): fac for fac in
                             facturas}
            for future in concurrent.futures.as_completed(future_to_rad):
                fac = future_to_rad[future]
                try:
                    result = future.result()
                    self.fill_and_save_total(result, fac)
                except Exception as exc:
                    print(f"num_aut={fac.numero_autorizacion!r} generated an exception: {str(exc)}")

            if self.errs:
                notify('task-fill-data',
                       f"Reporte de facturas con error al consultarse en API de Medicar",
                       f"Tarea ejecutada el {day_slash_month_year(datetime.datetime.now())}.\n"
                       f"Facturas con error al consultarse: {len(self.errs)}.\n {' '.join(self.errs)}")

    def fill_and_save_total(self, result: dict, fac: FacturasProcesadas):
        """
        Siendo result la respuesta de la API de medicar por medio de
        func(obtener_datos_formula). Se calcula el valor_total y se guarda en bd.
        :param result: Respuesta de API Medicar.
        :param fac: Modelo que representa Factura
        :return: None.
                 Caso haber error, la registra en lista self.errs con el concepto del error.
        """
        try:
            if isinstance(result, dict) and result and result != {'error': 'No se han encontrado registros.',
                                                                  'codigo': '1'}:
                total = self.calc_valor_total(result)
                log.info(f"Asignando {total=}. Guardando en bd {fac.factura=}.")
                fac.valor_total = total
                fac.save()
            else:
                log.error(f'No se pudo tomar datos de API para {fac.numero_autorizacion=}, {fac.factura=}.')
                self.errs.append(f'\t• {fac.factura} - {fac.numero_autorizacion}\n')
        except Exception as e:
            log.error(f'{result=}, Error={e}')
            self.errs.append(f'\t• {fac.factura} - {fac.numero_autorizacion}\n')

    def calc_valor_total(self, result):
        total = 0
        for art in result['articulos']:
            total_art = art['cantidad'] * art['costo_promedio']
            total += total_art
        return total


@dataclass
class FillExtraDataFbase:
    errs: list = field(init=False, default_factory=list)

    def get_facturas(self) -> QuerySet:
        """Busca facturas que serán actualizadas."""
        tod = datetime.datetime.now()
        end = (tod - datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59)
        return FacturasProcesadas.objects.filter(fecha_factura__lte=end, link_soporte=None).order_by('fecha_factura')

    def run(self, **kwargs):
        """Función principal llamada desde core.apps.tasks.utils.main que se encarga de
        actualizar el link_soporte del modelo FacturasProcesadas."""
        facturas = self.get_facturas()[:10]
        log.info(f"Iniciando llamados a Firebase para obtener link_soporte de {len(facturas)} actas.")
        self.firebase_calls(facturas)

    def firebase_calls(self, facturas: QuerySet[FacturasProcesadas]):
        """
        Llama asíncronamente la función get_firebase_acta.
        :param facturas: Facturas buscadas en bd con base lógica implementada en self.get_facturas()
        :return: None.
                Envia un correo en caso de haber problemas con facturas procesadas.
                Ej.:
                    - Firebase no respondió.
        """
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_rad = {executor.submit(get_firebase_acta, fac.acta): fac for fac in
                             facturas}
            for future in concurrent.futures.as_completed(future_to_rad):
                fac = future_to_rad[future]
                try:
                    result = future.result()
                    self.fill_and_save_acta(result, fac)
                except Exception as exc:
                    print(f"num_aut={fac.numero_autorizacion!r} generated an exception: {str(exc)}")

            if self.errs:
                notify('task-fill-data',
                       f"Reporte de actas con error al consultarse en Firebase",
                       f"Tarea ejecutada el {day_slash_month_year(datetime.datetime.now())}.\n"
                       f"Actas con error al consultarse: {len(self.errs)}.\n {' '.join(self.errs)}")

    def fill_and_save_acta(self, result: dict, fac: FacturasProcesadas):
        """
        Siendo result la respuesta de la llamada a Firebase por medio de
        func(get_firebase_acta). Se crea el link_soporte y se guarda en bd.
        :param result: Respuesta de Firebase.
        :param fac: Modelo que representa Factura
        :return: None.
                 Caso haber error, la registra en lista self.errs con el concepto del error.
        """
        try:
            if result:
                if result['state'] == 'Completed':
                    link_soporte = f"https://drive.google.com/file/d/{result['actFileId']}/view"
                    log.info(f"{link_soporte=}. Guardando en bd {fac.acta=}, {fac.factura=}.")
                    fac.link_soporte = link_soporte
                    fac.save()
                else:
                    log.info(f"'sin soporte de entrega digital'. Guardando en bd {fac.acta=}, {fac.factura=}.")
                    fac.link_soporte = 'sin soporte de entrega digital'
                    fac.save()
            else:
                log.error(f'No se pudo tomar datos de Fbase {fac.acta=}, {fac.numero_autorizacion=}, {result=}')
                self.errs.append(f'\t• {fac.factura=}, {fac.acta} - {fac.numero_autorizacion}.\n')
        except Exception as e:
            log.error(f'{result=}, Error={e}')
            self.errs.append(f'\t• {fac.factura=}, {fac.factura} - {fac.numero_autorizacion}.\n')


@dataclass
class Send2Cajacopi:
    errs: list = field(init=False, default_factory=list)

    def get_facturas(self) -> QuerySet:
        """Busca facturas que serán actualizadas."""
        tod = datetime.datetime.now()
        end = (tod - datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59)
        # TODO Validar si se van a consultar las facturas que ademas de tener el estado como None
        # tengan en su estado un error especifico. Por ejemplo, aquellas que tengan la palabra error
        # también seran consideradas?
        return FacturasProcesadas.objects.filter(
            fecha_factura__lte=end, estado=None, valor_total__isnull=False
        ).order_by('fecha_factura')

    def run(self, **kwargs) -> None:
        """Función principal llamada desde core.apps.tasks.utils.main que se encarga de
        actualizar los campos estado y resp_cajacopi del modelo FacturasProcesadas."""
        facturas = self.get_facturas()[:10]
        log.info(f"Iniciando llamados a CAJACOPI para actualizar estado de {len(facturas)} facturas.")
        self.cajacopi_calls(facturas)

    def cajacopi_calls(self, facturas: QuerySet[FacturasProcesadas]) -> None:
        """
        Llama asíncronamente la función update_status_factura_cajacopi
        para actualizar el estado en el sistema de cajacopi de procesado a activo
        de determinada factura
        :param facturas: Facturas buscadas en bd con base lógica implementada en self.get_facturas()
        :return: None.
                Envia un correo en caso de haber problemas con facturas procesadas.
                Ej.:
                    - Api no respondió y por eso no hubo respuesta a procesar.
                    - Api respondio con error referente a algo en el contenido de la petición.
        """
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_rad = {executor.submit(update_status_factura_cajacopi, fac.factura, fac.valor_total,
                                             fac.numero_autorizacion): fac for fac in
                             facturas}
            for future in concurrent.futures.as_completed(future_to_rad):
                fac = future_to_rad[future]
                try:
                    result = future.result()
                    self.fill_and_save_estado(result, fac)
                except Exception as exc:
                    print(f"num_aut={fac.numero_autorizacion!r} generated an exception: {str(exc)}")

            if self.errs:
                notify('task-fill-data',
                       f"Reporte de facturas con error al procesarse",
                       f"Tarea ejecutada el {day_slash_month_year(datetime.datetime.now())}.\n"
                       f"Facturas con error al consultarse: {len(self.errs)}.\n {' '.join(self.errs)}")

    def fill_and_save_estado(self, result: dict, fac: FacturasProcesadas):
        """
        Siendo result la respuesta de API de cajacopi por medio de
        func(update_status_factura_cajacopi). Se guarda en base de datos
        este resultado en el campo resp_cajacopi que es un json y un mensaje
        representativo en el campo estado.
        :param result: Respuesta de api de cajacopi al haberse cambiado el estado de una factura.
        :param fac: Modelo que representa Factura
        :return: None.
                 Caso haber error, la registra en lista self.errs con el concepto del error.
        """
        try:
            if result:
                if 'error' in result['mensaje'].lower():
                    log.error(f"Error al intentar procesar factura {fac.factura}: {result['mensaje']!r}.")
                    fac.estado = 'error al procesar factura'
                    fac.resp_cajacopi = result
                    fac.save()
                    self.errs.append(f"\t•  {fac.factura=}, {fac.valor_total=}, {fac.numero_autorizacion=}. {result['mensaje']}.\n")
                else:
                    log.info(f"Procesada con exito {fac.factura=}, {fac.valor_total=}, {fac.numero_autorizacion=}")
                    fac.estado = 'procesada con exito'
                    fac.resp_cajacopi = result
                    fac.save()
            else:
                log.error(f'No se pudo tomar datos de API Cajacopi {fac.factura=}, {fac.valor_total=}, {fac.numero_autorizacion=}')
                self.errs.append(f'\t•  {fac.factura=}, {fac.valor_total=}, {fac.numero_autorizacion=}. Problema con API.\n')
        except Exception as e:
            log.error(f'{result=}, Error={e}')
            self.errs.append(f'\t•  {fac.factura=}, {fac.valor_total=}, {fac.numero_autorizacion=}. Error: {e}\n')
