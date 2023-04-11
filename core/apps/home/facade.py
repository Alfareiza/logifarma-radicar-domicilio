from typing import List

from django.db.models import Count

from core.apps.base.models import Radicacion


def listar_radicados_mes(month: str, year: str = '2023') -> List[Radicacion]:
    """
    Lista todos los radicados de un mes ordenados decrescentemente.
    :param month: Obligatório. '04' o '12' o '10' ...
    :param year: Opcional. '2023'
    :return:
    """
    return list(Radicacion.objects.filter(
        datetime__year__gte=year,
        datetime__month__gte=month,
        datetime__year__lte=year,
        datetime__month__lte=month,
    ).values().order_by('-datetime'))


def order_radicados_by_mun_mes(month: str, year: str = '2023') -> list[dict]:
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
        datetime__year__gte=year,
        datetime__month__gte=month,
        datetime__year__lte=year,
        datetime__month__lte=month,
    ).values('municipio__name', "municipio__departamento").annotate(
        radicados=Count('id')
    ).order_by('-radicados'))


def encontrar_radicado(num):
    return Radicacion.objects.get(numero_radicado=num).values()
