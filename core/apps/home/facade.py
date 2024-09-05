from typing import List

from django.db.models import Count

from core.apps.base.models import Radicacion


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


def crecimiento_con_mes_anterior(current_day, current_hour, rads_current_month, rads_last_month) -> str:
    count_rads_last_month_until_current_day = rads_last_month.filter(
        datetime__day__lte=current_day).exclude(datetime__day=current_day, datetime__hour__gt=current_hour).count()
    count_rads_current_month_until_current_day = rads_current_month.filter(datetime__day__lte=current_day).count()
    crecimiento = int(round((
                                (count_rads_current_month_until_current_day - count_rads_last_month_until_current_day)
                                / count_rads_last_month_until_current_day
                        ) * 100, 2))
    return f"+{crecimiento}%" if crecimiento > 0 else f"{crecimiento}%"
