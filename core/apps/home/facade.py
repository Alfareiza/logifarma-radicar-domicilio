from typing import List

from django.db.models import Count

from core.apps.base.models import Radicacion


def listar_radicados_mes(month: str,
                         args=('datetime', 'numero_radicado', 'ip', 'paciente_cc'),
                         year: str = '2024') -> List[Radicacion]:
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


def listar_uniques_by_field(month: str, field: str, year: str = '2024') -> List[Radicacion]:
    """
    Lista todos los radicados de un mes sin repetir basado en el
    field.
    """
    return Radicacion.objects.filter(
        datetime__year=year,
        datetime__month=month,
    ).order_by(field).distinct(field)


def listar_radicados_old_months(month: str, year: str = '2024') -> List[Radicacion]:
    return Radicacion.objects.filter(
        datetime__year=year,
        datetime__month__lt=month
    ).values('ip', 'paciente_cc')


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
