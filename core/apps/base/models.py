from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    EmailField,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    JSONField,
    Model,
    PositiveBigIntegerField,
    PositiveIntegerField,
)


class Municipio(Model):
    name = CharField(max_length=128)
    departamento = CharField(max_length=128)

    class Meta:
        unique_together = ('name', 'departamento')
        ordering = ['departamento', 'name']

    def __str__(self):
        return f"{self.name.title()}, {self.departamento.title()}"


class Barrio(Model):
    name = CharField(max_length=128)
    zona = CharField(max_length=20, blank=False)
    municipio = ForeignKey(Municipio, blank=False, on_delete=CASCADE)
    cod_zona = IntegerField()
    status = IntegerField()

    class Meta:
        unique_together = ('municipio', 'name', 'zona', 'cod_zona')
        ordering = ['cod_zona', 'name']

    def __str__(self):
        return f"{self.name.title()} - Zona {self.zona.title()}"


class Radicacion(Model):
    datetime = DateTimeField(auto_now_add=True)
    numero = PositiveIntegerField(unique=True)
    municipio = ForeignKey(Municipio, on_delete=CASCADE)
    barrio = ForeignKey(Barrio, on_delete=CASCADE)
    celular_uno = PositiveBigIntegerField()
    celular_dos = PositiveBigIntegerField()
    email = EmailField(max_length=254)
    direccion = CharField(max_length=150)
    ip = GenericIPAddressField(protocol='both')

    # Campos de Paciente
    paciente_nombre = CharField(max_length=150)
    paciente_cedula = PositiveIntegerField()
    paciente_data = JSONField()

    # Campos de Domiciliario
    domiciliario_nombre = CharField(max_length=150, blank=True, null=True)
    domiciliario_identificacion = PositiveIntegerField(blank=True, null=True)
    domiciliario_empresa = CharField(max_length=150, blank=True, null=True)

    # Campos adicionales
    estado = CharField(max_length=64, blank=True, null=True)
    alistamiento = DateTimeField(blank=True, null=True)
    alistado_por = CharField(max_length=150, blank=True, null=True)
    despachado = DateTimeField(blank=True, null=True)
    acta_entrega = CharField(max_length=150, blank=True, null=True)
    factura = CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"{self.numero}"
