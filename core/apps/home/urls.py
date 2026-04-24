from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from core.apps.home import views

urlpatterns = [
    path('inicio/', views.index, name='index'),
    path('sinacta/', views.sinacta, name='sinacta'),
    path('buscador/', views.buscador, name='buscador'),
    path('radicacion/<int:pk>/', views.radicacion_detail, name='radicacion_detail_pk'),
    path('radicacion/<slug:ref>/', views.radicacion_detail, name='radicacion_detail'),
    path('soporte/<slug:value>', views.ver_soporte_rad, name='soporte'),
    # Authentication
    path('login/', csrf_exempt(views.UserLoginView.as_view()), name='login'),
    path('logout/', views.logout_view, name='logout'),
]
