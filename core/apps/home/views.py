import datetime

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from core.apps.base.resources.tools import decrypt
from core.apps.home import facade
from core.apps.home.context_processors import order_radicados_by_day
from core.apps.home.facade import order_radicados_by_mun_mes
from core.apps.home.forms import LoginForm
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
    if request.user.username not in ['admin', 'logistica']:
        logout(request)
        return redirect('base:home')
    radicados = facade.listar_radicados_mes(datetime.datetime.now().month)
    return render(request, "pages/index.html",
                  {
                      'radicados': radicados,
                      'radicados_day': {f"{k}": len(v) for k, v in order_radicados_by_day(radicados).items()},
                      'radicados_mun': order_radicados_by_mun_mes(datetime.datetime.now().month)
                   }
                  )


# Authentication
class UserLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm


def logout_view(request):
    logout(request)
    return redirect('/login/')
