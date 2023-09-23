from django.db.models import Model
from django.db.models import IntegerField, DateTimeField, CharField, JSONField


class FacturasProcesadas(Model):
    agregado = DateTimeField(auto_now_add=True)
    actualizado = DateTimeField(auto_now=True)
    factura = CharField(max_length=24, unique=True)
    fecha_factura = DateTimeField()
    acta = CharField(max_length=24)
    numero_autorizacion = CharField(unique=True, max_length=24)
    valor_total = IntegerField(blank=True, null=True)
    link_soporte = CharField(max_length=254, blank=True, null=True)
    estado = CharField(max_length=128, blank=True, null=True)
    resp_cajacopi = JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.factura} estado={self.estado!r}"

    class Meta:
        db_table = 'facturas_procesadas'
