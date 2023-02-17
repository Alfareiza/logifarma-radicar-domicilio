"""URL mappings for the base app (transaction app)"""

from django.urls import path

from core.apps.base.spark import Spark, finalizado_spark
from core.apps.base.views import ContactWizard, finalizado

app_name = 'base'

urlpatterns = [
    path('', ContactWizard.as_view(), name='home'),
    path('finalizado/', finalizado, name='done'),
    path('finalizado_spark/', finalizado_spark, name='done_spark'),
    path('spark/', Spark.as_view(), name='spark'),
]
