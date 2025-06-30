import datetime
from statistics import mean
from typing import List

from django.db.models import Count

from core.apps.base.models import Radicacion
from core.apps.home.utils import get_last_month_and_year


def listar_radicados_mes(month: int,
                         args=('datetime', 'numero_radicado', 'ip', 'paciente_cc'),
                         year: int = 2024) -> List[Radicacion]:
    """
    Lista todos los radicados de un mes ordenados decrescentemente.
    :param args:
    :param month: Obligatório. '04' o '12' o '10' ...
    :param year: Opcional. '2023'
    :return:
    """
    return Radicacion.objects.filter(
        datetime__year=year,
        datetime__month=month,
    ).order_by('-datetime').values(*args)


def listar_uniques_by_field(month: int, field: str, year: int = '2024') -> List[Radicacion]:
    """
    Lista todos los radicados de un mes sin repetir basado en el
    field.
    """
    return Radicacion.objects.filter(
        datetime__year=year,
        datetime__month=month,
    ).order_by(field).distinct(field)


def listar_radicados_old_months(month: int, year: int = 2024) -> List[Radicacion]:
    return Radicacion.objects.filter(
        datetime__year__lte=year,
        datetime__month__lt=month
    ).values('ip', 'paciente_cc', 'datetime')


def order_radicados_by_mun_mes(month: str, year: str = '2024') -> List[dict]:
    """
    Lista a cantidad de radicados por municipio en determinado mes/año
    :param month: Obligatório. '04' o '12' o '10' ...
    :param year: Opcional. '2023'
    :return:
            Ex.:
                [
                    {'municipio__name': 'barranquilla',
                      'municipio__departamento': 'atlántico',
                      'radicados': 504},
                     {'municipio__name': 'soledad',
                      'municipio__departamento': 'atlántico',
                      'radicados': 395},
                     {'municipio__name': 'villavicencio',
                      'municipio__departamento': 'meta',
                      'radicados': 274},
                     {'municipio__name': 'malambo',
                      'municipio__departamento': 'atlántico',
                      'radicados': 53},
                    ...
                    }
                ]
    """
    return list(Radicacion.objects.filter(
        datetime__year=year,
        datetime__month=month,
    ).values('municipio__name', "municipio__departamento").annotate(
        radicados=Count('id')
    ).order_by('-radicados'))


def encontrar_radicado(num):
    return Radicacion.objects.get(numero_radicado=num).values()


def qty_radicados_hasta_ahora(current_day, current_hour, rads_last_month) -> int:
    """Calcula la cantidad de radicados del mes anterior hasta el dia equivalente a hoy."""
    return rads_last_month.filter(
        datetime__day__lte=current_day).exclude(datetime__day=current_day, datetime__hour__gt=current_hour).count()


def crecimiento_con_mes_anterior(current_day, current_hour, rads_current_month, rads_last_month) -> str:
    count_rads_last_month_until_current_day = qty_radicados_hasta_ahora(current_day, current_hour, rads_last_month)
    count_rads_current_month_until_current_day = rads_current_month.filter(datetime__day__lte=current_day).count()
    if count_rads_last_month_until_current_day:
        crecimiento = int(round((
                                        (
                                                    count_rads_current_month_until_current_day - count_rads_last_month_until_current_day) / count_rads_last_month_until_current_day
                                ) * 100, 2))
    else:
        crecimiento = 0
    return f"+{crecimiento}%" if crecimiento > 0 else f"{crecimiento}%"


def radicados_sin_acta():
    dt = datetime.datetime.now()
    return Radicacion.objects.select_related('municipio').filter(acta_entrega=None).exclude(
        datetime__day=dt.day, datetime__month=dt.month, datetime__year=dt.year
    ).order_by('datetime')


def avg_last_n_months(n_months_back: int) -> int:
    """
    Calcula el promedio de radicados desde el mes anterior hacia atrás.
    :param n_months_back: Cantidad de meses a considerar en la query.
    Si se define 1, considera el mes anterior.
    Si se define 2, considera los dos meses anteriores.
    :return: Promedio de radicados de los  últimos n meses.
    """
    dt = datetime.datetime.now()
    qt_per_month = []
    for _ in range(n_months_back):
        last_year, last_month = get_last_month_and_year(dt)
        qt_per_month.append(listar_radicados_mes(month=last_month, year=last_year, args=('pk',)).count())
        dt = datetime.datetime(year=last_year, month=last_month, day=1)

    return int(mean(qt_per_month))
