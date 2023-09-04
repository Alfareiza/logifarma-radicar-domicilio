import csv

from django.contrib import admin
from django.http import HttpResponse

from core.apps.base.models import Municipio, Barrio, Med_Controlado


# Documentation
# https://docs.djangoproject.com/en/4.1/ref/contrib/admin/
@admin.action(description="Exportar elementos seleccionados en csv")
def export_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="export.csv"'

    writer = csv.writer(response)
    fields = [field.name for field in queryset.model._meta.fields]
    writer.writerow(fields)

    for obj in queryset:
        row = [getattr(obj, field) for field in fields]
        writer.writerow(row)

    return response


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ('name', 'departamento')
    list_filter = ('departamento',)
    search_fields = ('name',)
    ordering = ('name', 'departamento')
    actions = [export_csv]

    def save_model(self, request, obj, form, change):
        obj.save(using='server')


@admin.register(Barrio)
class BarrioAdmin(admin.ModelAdmin):
    list_display = ('name', 'zona', 'cod_zona', 'municipio')
    list_filter = ('municipio', 'zona', 'status')
    search_fields = ('name',)
    ordering = ('municipio', 'name', 'zona')
    raw_id_fields = ('municipio',)
    actions = [export_csv]

    def save_model(self, request, obj, form, change):
        obj.save(using='default')
        obj.save(using='server')


@admin.register(Med_Controlado)
class MedicamentoControladoAdmin(admin.ModelAdmin):
    exclude = ("field_one", 'field_two')
    list_display = ('nombre', 'cum', 'activo')
    list_filter = ('activo',)
    search_fields = ('name', 'cum')
    ordering = ('nombre', 'cum')
    actions = [export_csv]

    def save_model(self, request, obj, form, change):
        obj.save(using='default')
        obj.save(using='server')
