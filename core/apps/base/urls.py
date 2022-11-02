"""URL mappings for the base app (transaction app)"""

from django.urls import path
from core.apps.base.views import home, paso_a_paso, autorizacion_servicio, tomar_foto_formula_medica

app_name = 'base'

urlpatterns = [
	path('', home, name='home'),
	path('instrucciones/', paso_a_paso, name='paso_a_paso'),
	path('autorizacion/', autorizacion_servicio, name='autorizacion_servicio'),
	path('formula/', tomar_foto_formula_medica, name='tomar_foto_formula_medica'),	

]

