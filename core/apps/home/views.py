import datetime

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from core.apps.base.models import Radicacion
from core.apps.base.resources.tools import decrypt
from core.apps.home import facade
from core.apps.home.context_processors import order_radicados_by_day
from core.apps.home.facade import (
    avg_last_n_months,
    count_radicados_current_month_until_day,
    count_radicados_in_month_until_calendar_moment,
    format_crecimiento_pct,
    order_radicados_by_mun_mes,
)
from core.apps.home.forms import LoginForm
from core.apps.home.utils import (
    get_last_month_and_year,
    MES,
    month_end_exclusive,
    month_start_datetime,
)
from core.settings import logger


@csrf_exempt
@login_required
def ver_soporte_rad(request, value):
    rad, doc_id, ssc = value.split('aCmG')
    logger.info(f'{decrypt(rad)} {request.user.username}'
                ' consultando soporte de entrega.')
    logout(request)
    return redirect(f'https://drive.google.com/file/d/{doc_id[::-1]}/view')
    # return render(request, "pages/ver_pdf_soporte.html", {'doc_id': doc_id })


@login_required
def index(request):
    if request.user.username not in ('admin', 'logistica'):
        logger.warning(f'{request.user.username} ha accesado a inicio/ login.')
        logout(request)
        return redirect('base:home')
    dt = datetime.datetime.now()
    month_start = month_start_datetime(dt.year, dt.month)
    month_end = month_end_exclusive(dt.year, dt.month)

    radicados = list(
        Radicacion.objects.filter(
            datetime__gte=month_start,
            datetime__lt=month_end,
        )
        .order_by('-datetime')
        .values('datetime', 'numero_radicado', 'ip', 'paciente_cc', 'convenio')
    )

    unique_cc = {row['paciente_cc'] for row in radicados}
    qty_pacientes = len(unique_cc)

    if unique_cc:
        prior_cc = set(
            Radicacion.objects.filter(
                datetime__lt=month_start,
                paciente_cc__in=unique_cc,
            )
            .values_list('paciente_cc', flat=True)
            .distinct()
        )
        qty_new_pacientes = len(unique_cc - prior_cc)
    else:
        qty_new_pacientes = 0

    qty_medicamentos_autorizados = sum(
        1 for row in radicados if len(row['numero_radicado'] or '') < 15
    )
    qty_medicamentos_no_autorizados = sum(
        1 for row in radicados if len(row['numero_radicado'] or '') > 15
    )

    qty_pacientes_foneca = sum(
        1 for row in radicados if (row['convenio'] or '') == 'foneca'
    )
    qty_pacientes_fomag = sum(
        1 for row in radicados if (row['convenio'] or '') == 'fomag'
    )
    qty_pacientes_proteger = sum(
        1
        for row in radicados
        if (row['convenio'] or '') in ('proteger', 'cajacopi')
    )
    qty_pacientes_mutualser = sum(
        1 for row in radicados if (row['convenio'] or '') == 'mutualser'
    )

    last_year, last_month = get_last_month_and_year(dt)
    qty_rads_mes_anterior_hasta_current_day = (
        count_radicados_in_month_until_calendar_moment(
            last_year, last_month, dt.day, dt.hour
        )
    )
    count_rads_current_month_until_current_day = (
        count_radicados_current_month_until_day(dt.year, dt.month, dt.day)
    )
    crecimiento = format_crecimiento_pct(
        count_rads_current_month_until_current_day,
        qty_rads_mes_anterior_hasta_current_day,
    )

    return render(request, "pages/index.html",
                  {
                      'segment': 'Dashboard',
                      'parent': f'Radicados de {MES[dt.month]} del {dt.year}',
                      'radicados': radicados,
                      'radicados_day': {f"{k}": len(v) for k, v in order_radicados_by_day(radicados).items()},
                      'radicados_mun': order_radicados_by_mun_mes(dt.month, dt.year),
                      'qty_pacientes': qty_pacientes,
                      'qty_new_pacientes': qty_new_pacientes,
                      'porcentaje_crecimiento': crecimiento,
                      'qty_rads_mes_anterior_hasta_current_day': qty_rads_mes_anterior_hasta_current_day,
                      'qty_medicamentos_autorizados': qty_medicamentos_autorizados,
                      'qty_medicamentos_no_autorizados': qty_medicamentos_no_autorizados,
                      'qty_pacientes_foneca': qty_pacientes_foneca,
                      'qty_pacientes_fomag': qty_pacientes_fomag,
                      'qty_pacientes_proteger': qty_pacientes_proteger,
                      'qty_pacientes_mutualser': qty_pacientes_mutualser,
                      'avg_last_six_months': avg_last_n_months(6),
                  }
                  )


def sinacta(request):
    radicados = facade.radicados_sin_acta()
    return render(request, "pages/tables.html",
                  {
                      'segment': '',
                      'parent': 'Radicados sin acta de entrega',
                      'radicados': radicados
                  })


@login_required
def buscador(request):
    return render(request, "pages/buscador.html", {
                      'segment': 'Buscador', 'parent': 'Buscador de usuarios'})


@login_required
def radicacion_detail(request, pk: int | None = None, ref: str | None = None):
    """
    Operational detail view for a single Radicacion.

    Supports both URL shapes:
    - /radicacion/<int:pk>/
    - /radicacion/<slug:ref>/ where ref is either numero_radicado or F{pk}
    """
    if pk is None and ref is None:
        return redirect('index')

    qs = Radicacion.objects.select_related('municipio', 'barrio')

    if pk is not None:
        rad = get_object_or_404(qs, pk=pk)
    else:
        if isinstance(ref, str) and ref.startswith('F') and ref[1:].isdigit():
            rad = get_object_or_404(qs, pk=int(ref[1:]))
        else:
            rad = get_object_or_404(qs, numero_radicado=str(ref))

    next_rad = rad.get_next_radicacion()
    next_rad_url = next_rad.get_absolute_url() if next_rad else None
    next_sin_acta = rad.get_next_radicacion_sin_acta()
    next_sin_acta_url = next_sin_acta.get_absolute_url() if next_sin_acta else None
    previous_rad = rad.get_previous_radicacion()
    previous_rad_url = previous_rad.get_absolute_url() if previous_rad else None
    previous_sin_acta = rad.get_previous_radicacion_sin_acta()
    previous_sin_acta_url = previous_sin_acta.get_absolute_url() if previous_sin_acta else None

    return render(request, "pages/radicacion_detail.html", {
        # 'segment': 'Detalle de Radicación',
        'parent': f'Radicación {rad.numero_autorizacion} · {rad.convenio.title()}',
        'rad': rad,
        'preview_url': rad.foto_formula,
        'next_radicacion_url': next_rad_url,
        'next_sin_acta_url': next_sin_acta_url,
        'previous_radicacion_url': previous_rad_url,
        'previous_sin_acta_url': previous_sin_acta_url,
    })


# Authentication
class UserLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm


def logout_view(request):
    logout(request)
    return redirect('/login/')
