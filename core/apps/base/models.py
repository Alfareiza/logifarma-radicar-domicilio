from django.db.models import (
    BooleanField, CASCADE,
    CharField,
    DateTimeField,
    EmailField,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    JSONField,
    Model,
    PositiveBigIntegerField,
    PositiveIntegerField, DateField,
)


class Municipio(Model):
    name = CharField(max_length=128)
    departamento = CharField(max_length=128)
    cod_dane = IntegerField(null=True, blank=True)
    activo = BooleanField(default=False)

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
    # creado = DateTimeField(blank=True, null=True)

    numero_radicado = CharField(unique=True, max_length=24)
    municipio = ForeignKey(Municipio, on_delete=CASCADE)
    barrio = ForeignKey(Barrio, on_delete=CASCADE)
    cel_uno = CharField(max_length=24, blank=True, null=True)
    cel_dos = CharField(max_length=24, blank=True, null=True)
    email = EmailField(max_length=254)
    direccion = CharField(max_length=150)
    ip = GenericIPAddressField(protocol='both')

    # Campos de Paciente
    paciente_nombre = CharField(max_length=150)
    paciente_cc = CharField(max_length=32)
    paciente_data = JSONField()

    # Campos de Domiciliario
    domiciliario_nombre = CharField(max_length=150, blank=True, null=True)
    domiciliario_ide = CharField(max_length=25, blank=True, null=True)
    domiciliario_empresa = CharField(max_length=150, blank=True, null=True)

    # Campos adicionales
    estado = CharField(max_length=64, blank=True, null=True)
    alistamiento = DateTimeField(blank=True, null=True)
    alistado_por = CharField(max_length=150, blank=True, null=True)
    despachado = DateTimeField(blank=True, null=True)
    acta_entrega = CharField(max_length=150, blank=True, null=True)
    factura = CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"{self.id}"



class Med_Controlado(Model):
    cum = CharField(max_length=24)
    nombre = CharField(max_length=250)
    activo = BooleanField(default=True)
    field_one = CharField(max_length=24, blank=True, null=True)
    field_two = CharField(max_length=24, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Medicamentos Controlados"
        verbose_name = "medicamento controlado"

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.lower()
        return super(Med_Controlado, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.cum} - {self.nombre}"


class Inventario(Model):
    created_at = DateTimeField(auto_now_add=True)
    centro = CharField(max_length=24)
    cod_mol = CharField(max_length=24)
    cod_barra = CharField(max_length=128)
    cum = CharField(max_length=64, blank=True, null=True)
    descripcion = CharField(max_length=250)
    lote = CharField(max_length=24)
    fecha_vencimiento = DateField()
    inventario = IntegerField()
    costo_promedio = IntegerField()
    cantidad_empaque = IntegerField()

    def __str__(self):
        return f"{self.descripcion} ({self.inventario})"


class Centro(Model):
    disp = CharField(max_length=24)
    bod = CharField(max_length=24)
    drogueria = CharField(max_length=128)
    correo_coordinador = CharField(max_length=128, blank=True, null=True)
    dia_ped = CharField(max_length=24, blank=True, null=True)
    estado = CharField(max_length=24, blank=True, null=True)
    modalidad = CharField(max_length=24)
    poblacion = IntegerField(blank=True, null=True)
    municipio = ForeignKey(Municipio, on_delete=CASCADE)
    tipo = CharField(max_length=24)
    correo_disp = CharField(max_length=128, blank=True, null=True)
    responsable = CharField(max_length=128, blank=True, null=True)
    cedula = CharField(max_length=64, blank=True, null=True)
    celular = CharField(max_length=64, blank=True, null=True)
    direccion = CharField(max_length=128, blank=True, null=True)
    medicar = CharField(max_length=8, blank=True, null=True)
    tent = IntegerField()
    analista = CharField(max_length=128, blank=True, null=True)
    ult_fecha_disp = DateTimeField(blank=True, null=True)
    aux_pqr = CharField(max_length=128, blank=True, null=True)
    transp_1 = CharField(max_length=128, blank=True, null=True)
    transp_2 = CharField(max_length=128, blank=True, null=True)
    correo_contacto_eps = CharField(max_length=128, blank=True, null=True)

    class Meta:
        db_table = 'base_centros'

    def __str__(self):
        return f"{self.disp} - {self.drogueria}"
