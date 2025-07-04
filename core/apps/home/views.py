import datetime

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models.functions import Length
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from core.apps.base.resources.tools import decrypt
from core.apps.home import facade
from core.apps.home.context_processors import order_radicados_by_day
from core.apps.home.facade import order_radicados_by_mun_mes, avg_last_n_months
from core.apps.home.forms import LoginForm
from core.apps.home.utils import get_last_month_and_year, MES
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
    logger.warning(f'{request.user.username} ha accesado a inicio/ login.')
    if request.user.username not in ('admin', 'logistica'):
        logout(request)
        return redirect('base:home')
    dt = datetime.datetime.now()
    radicados = facade.listar_radicados_mes(month=dt.month, year=dt.year)
    unique_pacientes_in_month = facade.listar_uniques_by_field(month=dt.month, year=dt.year, field='paciente_cc')
    old_radicados = facade.listar_radicados_old_months(month=dt.month, year=dt.year)
    qty_new_pacientes = unique_pacientes_in_month.exclude(
        paciente_cc__in=old_radicados.values_list('paciente_cc', flat=True)
    )

    qty_medicamentos_autorizados = radicados.annotate(text_len=Length('numero_radicado')).filter(text_len__lt=15)
    qty_medicamentos_no_autorizados = radicados.annotate(text_len=Length('numero_radicado')).filter(text_len__gt=15)
    last_year, last_month = get_last_month_and_year(dt)
    rads_last_month = facade.listar_radicados_mes(month=last_month, year=last_year, args=('pk',))
    qty_rads_mes_anterior_hasta_current_day = facade.qty_radicados_hasta_ahora(dt.day, dt.hour, rads_last_month)
    crecimiento = facade.crecimiento_con_mes_anterior(dt.day, dt.hour, radicados, rads_last_month)

    return render(request, "pages/index.html",
                  {
                      'segment': 'Dashboard',
                      'parent': f'Radicados de {MES[dt.month]} del {dt.year}',
                      'radicados': radicados,
                      'radicados_day': {f"{k}": len(v) for k, v in order_radicados_by_day(radicados).items()},
                      'radicados_mun': order_radicados_by_mun_mes(dt.month),
                      'qty_pacientes': unique_pacientes_in_month.count(),
                      'qty_new_pacientes': qty_new_pacientes.count(),
                      'porcentaje_crecimiento': crecimiento,
                      'qty_rads_mes_anterior_hasta_current_day': qty_rads_mes_anterior_hasta_current_day,
                      'qty_medicamentos_autorizados': qty_medicamentos_autorizados.count(),
                      'qty_medicamentos_no_autorizados': qty_medicamentos_no_autorizados.count(),
                      'qty_pacientes_fomag': radicados.filter(convenio='fomag').count(),
                      'qty_pacientes_cajacopi': radicados.filter(convenio='cajacopi').count(),
                      'qty_pacientes_mutualser': radicados.filter(convenio='mutualser').count(),
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


# Authentication
class UserLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm


def logout_view(request):
    logout(request)
    return redirect('/login/')
