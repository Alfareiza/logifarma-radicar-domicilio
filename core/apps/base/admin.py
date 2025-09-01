import csv

from django.contrib import admin
from django.http import HttpResponse
from django import forms

from core.apps.base.models import Municipio, Barrio, Med_Controlado, CelularesRestringidos
from core.settings import logger


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


@admin.action(description="Cambiar estado 'activo' de elementos seleccionados.")
def toggle_activo(modeladmin, request, queryset):
    # Loop through selected municipios and toggle the 'activo' attribute
    for municipio in queryset:
        municipio.activo = not municipio.activo
        municipio.save()

    # Display a message to the user
    modeladmin.message_user(request, "Estado 'activo' de municipio(s) ha(n) sido cambiado con éxito.")


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ('name', 'cod_dane', 'departamento', 'activo')
    list_filter = ('departamento', 'activo')
    search_fields = ('name', 'cod_dane')
    ordering = ('name', 'departamento')
    actions = [export_csv, toggle_activo]


@admin.register(Barrio)
class BarrioAdmin(admin.ModelAdmin):
    list_display = ('name', 'zona', 'cod_zona', 'municipio')
    list_filter = ('municipio', 'zona', 'status')
    search_fields = ('name',)
    ordering = ('municipio', 'name', 'zona')
    raw_id_fields = ('municipio',)
    actions = [export_csv]


@admin.register(Med_Controlado)
class MedicamentoControladoAdmin(admin.ModelAdmin):
    exclude = ("field_one", 'field_two')
    list_display = ('nombre', 'cum', 'activo')
    list_filter = ('activo',)
    search_fields = ('name', 'cum')
    ordering = ('nombre', 'cum')
    actions = [export_csv]


@admin.register(CelularesRestringidos)
class CelularesRestringidosAdmin(admin.ModelAdmin):
    list_display = ('registrado_por', 'numero', 'motivo')
    list_filter = ('registrado_por',)
    search_fields = ('registrado_por__username', 'numero')
    ordering = ('registrado_por',)
    exclude = ('registrado_por',)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.registrado_por = request.user
        obj.save()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['numero'].widget.attrs['style'] = 'width: 250px;'
        return form
