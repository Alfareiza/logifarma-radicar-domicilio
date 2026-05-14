import calendar
import datetime
from statistics import mean
from typing import List

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth

from core.apps.base.models import Radicacion
from core.apps.home.utils import get_last_month_and_year, month_end_exclusive, month_start_datetime


def listar_radicados_mes(
    month: int,
    args=('datetime', 'numero_radicado', 'ip', 'paciente_cc'),
    year: int = 2024,
) -> List[Radicacion]:
    """
    Lista todos los radicados de un mes ordenados decrescentemente.
    Uses datetime range filters so the DB can use indexes on `datetime`.
    """
    start = month_start_datetime(year, month)
    end = month_end_exclusive(year, month)
    return Radicacion.objects.filter(
        datetime__gte=start,
        datetime__lt=end,
    ).order_by('-datetime').values(*args)


def listar_uniques_by_field(month: int, field: str, year: int = 2024):
    """
    Lista todos los radicados de un mes sin repetir basado en el field.
    """
    start = month_start_datetime(year, month)
    end = month_end_exclusive(year, month)
    return Radicacion.objects.filter(
        datetime__gte=start,
        datetime__lt=end,
    ).order_by(field).distinct(field)


def listar_radicados_old_months(month: int, year: int = 2024):
    """Radicados estrictamente anteriores al inicio del mes calendario dado."""
    month_start = month_start_datetime(year, month)
    return Radicacion.objects.filter(datetime__lt=month_start).values(
        'ip', 'paciente_cc', 'datetime'
    )


def order_radicados_by_mun_mes(month: int, year: int) -> List[dict]:
    """
    Lista la cantidad de radicados por municipio en determinado mes/año.
    """
    start = month_start_datetime(year, month)
    end = month_end_exclusive(year, month)
    return list(
        Radicacion.objects.filter(datetime__gte=start, datetime__lt=end)
        .values('municipio__name', 'municipio__departamento')
        .annotate(radicados=Count('id'))
        .order_by('-radicados')
    )


def encontrar_radicado(num):
    return Radicacion.objects.get(numero_radicado=num).values()


def count_radicados_in_month_until_calendar_moment(
    year: int, month: int, ref_day: int, ref_hour: int
) -> int:
    """
    Count radicados in [month_start, month_end) up to the same calendar day/hour
    as the reference, clamping the day to the last day of that month.
    """
    start = month_start_datetime(year, month)
    end = month_end_exclusive(year, month)
    last_dom = calendar.monthrange(year, month)[1]
    eff_day = min(ref_day, last_dom)
    return (
        Radicacion.objects.filter(datetime__gte=start, datetime__lt=end)
        .filter(
            Q(datetime__day__lt=eff_day)
            | Q(datetime__day=eff_day, datetime__hour__lte=ref_hour)
        )
        .count()
    )


def count_radicados_current_month_until_day(
    year: int, month: int, current_day: int
) -> int:
    """Radicados del mes desde el inicio hasta el día del mes (inclusive), clamped."""
    start = month_start_datetime(year, month)
    end = month_end_exclusive(year, month)
    last_dom = calendar.monthrange(year, month)[1]
    eff_day = min(current_day, last_dom)
    return Radicacion.objects.filter(
        datetime__gte=start,
        datetime__lt=end,
        datetime__day__lte=eff_day,
    ).count()


def qty_radicados_hasta_ahora(current_day, current_hour, rads_last_month) -> int:
    """DEPRECATED: kept for backwards compatibility; prefer count helpers above."""
    return rads_last_month.filter(
        datetime__day__lte=current_day
    ).exclude(
        datetime__day=current_day, datetime__hour__gt=current_hour
    ).count()


def crecimiento_con_mes_anterior(
    current_day, current_hour, rads_current_month, rads_last_month
) -> str:
    """DEPRECATED: kept for backwards compatibility."""
    count_rads_last_month_until_current_day = qty_radicados_hasta_ahora(
        current_day, current_hour, rads_last_month
    )
    count_rads_current_month_until_current_day = rads_current_month.filter(
        datetime__day__lte=current_day
    ).count()
    return format_crecimiento_pct(
        count_rads_current_month_until_current_day,
        count_rads_last_month_until_current_day,
    )


def format_crecimiento_pct(current_count: int, previous_count: int) -> str:
    """Build the '+X%' / '-X%' growth label used on the dashboard."""
    if previous_count:
        crecimiento = int(
            round(
                ((current_count - previous_count) / previous_count) * 100,
                2,
            )
        )
    else:
        crecimiento = 0
    return f'+{crecimiento}%' if crecimiento > 0 else f'{crecimiento}%'


def radicados_sin_acta():
    dt = datetime.datetime.now()
    return (
        Radicacion.objects.select_related('municipio')
        .filter(acta_entrega=None)
        .exclude(
            datetime__day=dt.day,
            datetime__month=dt.month,
            datetime__year=dt.year,
        )
        .order_by('datetime')
    )


def avg_last_n_months(n_months_back: int) -> int:
    """
    Promedio de radicados de los últimos n meses calendario previos al mes actual.
    Un solo agrupamiento por mes en DB en lugar de N queries COUNT.
    """
    if n_months_back <= 0:
        return 0

    now = datetime.datetime.now()
    cur_y, cur_m = now.year, now.month
    range_end = month_start_datetime(cur_y, cur_m)

    y, m = cur_y, cur_m
    months: list[tuple[int, int]] = []
    for _ in range(n_months_back):
        y, m = get_last_month_and_year(datetime.datetime(y, m, 1))
        months.append((y, m))

    range_start = month_start_datetime(y, m)

    rows = (
        Radicacion.objects.filter(datetime__gte=range_start, datetime__lt=range_end)
        .annotate(m=TruncMonth('datetime'))
        .values('m')
        .annotate(c=Count('id'))
    )
    count_by_trunc = {row['m']: row['c'] for row in rows}

    qt_per_month = []
    for yy, mm in months:
        key_dt = month_start_datetime(yy, mm)
        qt_per_month.append(count_by_trunc.get(key_dt, 0))

    return int(mean(qt_per_month))
