from django.contrib import admin

from core.apps.base.models import Municipio, Barrio


# Documentation
# https://docs.djangoproject.com/en/4.1/ref/contrib/admin/

@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ('name', 'departamento')
    list_filter = ('departamento',)
    search_fields = ('name',)
    ordering = ('name', 'departamento')


@admin.register(Barrio)
class BarrioAdmin(admin.ModelAdmin):
    list_display = ('name', 'zona', 'cod_zona', 'municipio')
    list_filter = ('municipio', 'zona', 'status')
    search_fields = ('name',)
    ordering = ('municipio', 'name', 'zona')
    raw_id_fields = ('municipio',)
