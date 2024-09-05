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
from core.apps.home.facade import order_radicados_by_mun_mes
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
    crecimiento = facade.crecimiento_con_mes_anterior(
        dt.day, dt.hour, radicados, facade.listar_radicados_mes(month=last_month, year=last_year, args=('pk',))
    )

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
                      'qty_medicamentos_autorizados': qty_medicamentos_autorizados.count(),
                      'qty_medicamentos_no_autorizados': qty_medicamentos_no_autorizados.count(),
                      'qty_pacientes_fomag': radicados.filter(convenio='fomag').count(),
                      'qty_pacientes_cajacopi': radicados.filter(convenio='cajacopi').count()
                  }
                  )
def sinacta(request):
    radicados = facade.radicados_sin_acta()
    return render(request, "pages/tables.html",
                  {
                      'segment': '',
                      'parent': f'Radicados sin acta de entrega',
                      'radicados': radicados
                  })


# Authentication
class UserLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm


def logout_view(request):
    logout(request)
    return redirect('/login/')
