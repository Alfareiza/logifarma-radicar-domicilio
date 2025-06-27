# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models

from core.settings import logger


class AdhosSires(models.Model):
    idadhos = models.AutoField(primary_key=True)
    turno = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    atendido = models.CharField(max_length=2, blank=True, null=True)
    caf = models.IntegerField(blank=True, null=True)
    usuario = models.CharField(max_length=50, blank=True, null=True)
    ventanilla = models.CharField(max_length=20, blank=True, null=True)
    hora_atencion = models.DateTimeField(blank=True, null=True)
    llamando = models.CharField(max_length=2, blank=True, null=True)
    consultorio = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'adhos_sires'


class Afiliados(models.Model):
    eps = models.TextField(blank=True, null=True)
    numero_documento = models.TextField(blank=True, null=True)
    tipo_documento = models.TextField(blank=True, null=True)
    nombres = models.TextField(blank=True, null=True)
    apellidos = models.TextField(blank=True, null=True)
    sexo = models.TextField(blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    departamento = models.TextField(blank=True, null=True)
    municipio = models.TextField(blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.TextField(blank=True, null=True)
    tipo_beneficiario = models.TextField(blank=True, null=True)
    codigo_ips = models.TextField(blank=True, null=True)
    categoria = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'afiliados'


class Afiliadosmagisterio(models.Model):
    num_doc = models.CharField(unique=True, max_length=30)
    tipo_doc = models.CharField(max_length=50)
    primer_nom = models.CharField(max_length=50)
    segundonom = models.CharField(max_length=50, blank=True, null=True)
    primer_ape = models.CharField(max_length=50)
    segundo_ape = models.CharField(max_length=50)
    sexo = models.CharField(max_length=15)
    fecha_naci = models.DateField()
    edad_cumplida = models.IntegerField()
    fecha_afil = models.DateField()
    tipo_afiliado = models.CharField(max_length=100)
    direccion_residencia = models.CharField(max_length=150, blank=True, null=True)
    dpto_atencion = models.CharField(max_length=50)
    mpio_atencion = models.CharField(max_length=50)
    ips_atencion = models.CharField(max_length=100)
    asegurador = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'afiliadosmagisterio'


class Afiliadosmutualser(models.Model):
    codigoentidad = models.CharField(max_length=100, blank=True, null=True)
    regimen = models.CharField(max_length=100, blank=True, null=True)
    tdoccabeza = models.CharField(max_length=100, blank=True, null=True)
    doccabeza = models.CharField(max_length=100, blank=True, null=True)
    tdocumento = models.CharField(max_length=100, blank=True, null=True)
    documento = models.CharField(unique=True, max_length=100, blank=True, null=True)
    primerapellido = models.CharField(max_length=100, blank=True, null=True)
    segundoapellido = models.CharField(max_length=100, blank=True, null=True)
    primernombre = models.CharField(max_length=100, blank=True, null=True)
    segundonombre = models.CharField(max_length=100, blank=True, null=True)
    fechanacimiento = models.DateField(blank=True, null=True)
    edad = models.IntegerField(blank=True, null=True)
    sexo = models.CharField(max_length=10, blank=True, null=True)
    id_poblacional = models.CharField(max_length=100, blank=True, null=True)
    grupopoblacional = models.CharField(max_length=100, blank=True, null=True)
    coddpto = models.CharField(max_length=10, blank=True, null=True)
    codmpio = models.CharField(max_length=10, blank=True, null=True)
    departamento = models.CharField(max_length=100, blank=True, null=True)
    municipio = models.CharField(max_length=100, blank=True, null=True)
    zona = models.CharField(max_length=100, blank=True, null=True)
    discapacidad = models.CharField(max_length=100, blank=True, null=True)
    catsisben = models.CharField(max_length=100, blank=True, null=True)
    fichasisben = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=100, blank=True, null=True)
    direccion = models.CharField(max_length=150, blank=True, null=True)
    barrio = models.CharField(max_length=100, blank=True, null=True)
    telefono1 = models.CharField(max_length=100, blank=True, null=True)
    celular = models.CharField(max_length=100, blank=True, null=True)
    correo = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'afiliadosmutualser'


class Artcapitacomplementaria(models.Model):
    codbarra = models.CharField(max_length=50, blank=True, null=True)
    codmol = models.CharField(max_length=50, blank=True, null=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'artcapitacomplementaria'


class Articulos(models.Model):
    codigo_molecula = models.TextField(blank=True, null=True)
    molecula = models.TextField(blank=True, null=True)
    concentracion = models.TextField(blank=True, null=True)
    forma_farmaceutica = models.TextField(blank=True, null=True)
    plu_cadena = models.TextField(blank=True, null=True)
    descripcion_molecula_medicar = models.TextField(blank=True, null=True)
    descripcion_articulo_medicar = models.TextField(blank=True, null=True)
    unidad_medida_completa = models.TextField(blank=True, null=True)
    contenido = models.TextField(blank=True, null=True)
    unidad_minima_contenido = models.TextField(blank=True, null=True)
    cantidad_presentacion = models.TextField(blank=True, null=True)
    unidad_minima_venta = models.TextField(blank=True, null=True)
    cantidad_blister = models.TextField(blank=True, null=True)
    precio_unidad_minima_con_iva = models.TextField(blank=True, null=True)
    precio_unidad_medida_venta = models.TextField(blank=True, null=True)
    precio_unidad_completa = models.TextField(blank=True, null=True)
    costo_unidad_minima = models.TextField(blank=True, null=True)
    porcentaje_iva = models.TextField(blank=True, null=True)
    opcion_cadena = models.TextField(blank=True, null=True)
    convenio = models.TextField(blank=True, null=True)
    plan = models.TextField(blank=True, null=True)
    subplan = models.TextField(blank=True, null=True)
    id_splan = models.TextField(blank=True, null=True)
    laboratorio = models.TextField(blank=True, null=True)
    nit = models.TextField(blank=True, null=True)
    ean = models.TextField(blank=True, null=True)
    cum = models.TextField(blank=True, null=True)
    atc = models.TextField(blank=True, null=True)
    registro_invima = models.TextField(blank=True, null=True)
    codigo_insumos = models.TextField(blank=True, null=True)
    tipo_medicamento = models.TextField(blank=True, null=True)
    marca = models.TextField(blank=True, null=True)
    field_precio_unidad_minima_con_iva = models.CharField(db_column=' Precio_Unidad_Minima_con_Iva', max_length=50,
                                                          blank=True,
                                                          null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it started with '_'.

    class Meta:
        managed = False
        db_table = 'articulos'


class Cargos(models.Model):
    cod_cargo = models.CharField(max_length=20, blank=True, null=True)
    cargo = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cargos'


class Centros(models.Model):
    coddisp = models.IntegerField(blank=True, null=True)
    disp_bod = models.CharField(db_column='Disp/Bod', max_length=100, blank=True,
                                null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    dispensario = models.CharField(max_length=100, blank=True, null=True)
    email_coordinador_a_field = models.CharField(db_column='Email_Coordinador(a)', max_length=100, blank=True,
                                                 null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    diaped = models.CharField(max_length=10, blank=True, null=True)
    estado = models.CharField(max_length=50, blank=True, null=True)
    modalidad = models.CharField(max_length=50, blank=True, null=True)
    dpto = models.CharField(max_length=50, blank=True, null=True)
    municipio = models.CharField(max_length=100, blank=True, null=True)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    correodisp = models.CharField(max_length=100, blank=True, null=True)
    responsable = models.CharField(max_length=100, blank=True, null=True)
    cedula = models.IntegerField(blank=True, null=True)
    celular = models.CharField(max_length=50, blank=True, null=True)
    dirección = models.CharField(max_length=200, blank=True, null=True)
    medicar = models.BooleanField(blank=True, null=True)
    tent = models.CharField(max_length=100, blank=True, null=True)
    analista = models.CharField(max_length=100, blank=True, null=True)
    ult_fec_disp = models.DateField(db_column='Ult_Fec_Disp', blank=True, null=True)  # Field name made lowercase.
    aux_pqr = models.CharField(max_length=100, blank=True, null=True)
    transp1 = models.CharField(max_length=50, blank=True, null=True)
    transp2 = models.CharField(max_length=50, blank=True, null=True)
    abrevmun = models.CharField(max_length=50, blank=True, null=True)
    contaceps = models.CharField(max_length=100, blank=True, null=True)
    caf = models.CharField(max_length=10, blank=True, null=True)
    field_poblacion = models.FloatField(db_column=' poblacion', blank=True,
                                        null=True)  # Field renamed to remove unsuitable characters. Field renamed because it started with '_'.

    class Meta:
        managed = False
        db_table = 'centros'


class Domicilios(models.Model):
    fecha_solicitud = models.DateField(blank=True, null=True)
    hora_solicitud = models.TimeField(blank=True, null=True)
    fecha_radicacion = models.DateField()
    hora_radicacion = models.TimeField()
    autorizacion = models.CharField(unique=True, max_length=300)
    mipres = models.CharField(max_length=400, blank=True, null=True)
    fecha_aut = models.DateField(blank=True, null=True)
    estado_aut = models.CharField(max_length=200, blank=True, null=True)
    acta = models.CharField(unique=True, max_length=300)
    fecha_acta = models.DateField(blank=True, null=True)
    hora_acta = models.TimeField(blank=True, null=True)
    factura = models.CharField(unique=True, max_length=300, blank=True, null=True)
    fecha_factura = models.DateField(blank=True, null=True)
    hora_factura = models.TimeField(blank=True, null=True)
    tipo_doc = models.CharField(max_length=150)
    documento = models.CharField(max_length=300)
    nombre_afiliado = models.CharField(max_length=300)
    p_nombre = models.CharField(max_length=200)
    s_nombre = models.CharField(max_length=200, blank=True, null=True)
    p_apellido = models.CharField(max_length=200)
    s_apellido = models.CharField(max_length=200)
    estado_afiliado = models.CharField(max_length=200)
    sede_afiliado = models.CharField(max_length=400, blank=True, null=True)
    regimen = models.CharField(max_length=400)
    dir_aut = models.CharField(max_length=400, blank=True, null=True)
    email_aut = models.CharField(max_length=300, blank=True, null=True)
    tel_aut = models.CharField(max_length=300, blank=True, null=True)
    cel_aut = models.CharField(max_length=300, blank=True, null=True)
    medico = models.CharField(max_length=400, blank=True, null=True)
    diagnostico = models.CharField(max_length=300, blank=True, null=True)
    archivo = models.CharField(max_length=300, blank=True, null=True)
    ips_solicita = models.CharField(max_length=300, blank=True, null=True)
    observacion = models.CharField(max_length=500, blank=True, null=True)
    responsable_guarda = models.CharField(max_length=400, blank=True, null=True)
    email_guarda = models.CharField(max_length=300, blank=True, null=True)
    responsable_aut = models.CharField(max_length=300, blank=True, null=True)
    email_res_aut = models.CharField(max_length=300, blank=True, null=True)
    celular1 = models.CharField(max_length=200)
    celular2 = models.CharField(max_length=200, blank=True, null=True)
    email_entrega = models.CharField(max_length=300, blank=True, null=True)
    direccion_entrega = models.CharField(max_length=300)
    departamento_entrega = models.CharField(max_length=300)
    municipio_entrega = models.CharField(max_length=300)
    barrio_entrega = models.CharField(max_length=300)
    usuario_radica = models.CharField(max_length=300)
    fecha_asignacion = models.DateField(blank=True, null=True)
    hora_asignacion = models.TimeField(blank=True, null=True)
    usuario_asignacion = models.CharField(max_length=300, blank=True, null=True)
    ed_ruta = models.CharField(max_length=300, blank=True, null=True)
    id_domiciliario = models.CharField(max_length=300, blank=True, null=True)
    domiciliario = models.CharField(max_length=300, blank=True, null=True)
    empresa_domicilio = models.CharField(max_length=300, blank=True, null=True)
    fecha_entrega = models.DateField(blank=True, null=True)
    hora_entrega = models.TimeField(blank=True, null=True)
    link_soporte = models.CharField(max_length=300, blank=True, null=True)
    usuario_rad_factura = models.CharField(max_length=300, blank=True, null=True)
    fecha_rad_factura = models.CharField(max_length=300, blank=True, null=True)
    hora_rad_factura = models.CharField(max_length=300, blank=True, null=True)
    convenio = models.CharField(max_length=50, blank=True, null=True)
    estado_entrega = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'domicilios'


class FacturasProcesadas(models.Model):
    id = models.BigAutoField(primary_key=True)
    agregado = models.DateTimeField()
    actualizado = models.DateTimeField()
    factura = models.CharField(unique=True, max_length=24)
    fecha_factura = models.DateTimeField()
    acta = models.CharField(max_length=24)
    numero_autorizacion = models.CharField(unique=True, max_length=24)
    valor_total = models.IntegerField(blank=True, null=True)
    link_soporte = models.CharField(max_length=254, blank=True, null=True)
    estado = models.CharField(max_length=128, blank=True, null=True)
    resp_cajacopi = models.JSONField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'facturas_procesadas'


class General(models.Model):
    idgeneral = models.AutoField(primary_key=True)
    turno = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    atendido = models.CharField(max_length=2, blank=True, null=True)
    caf = models.IntegerField(blank=True, null=True)
    usuario = models.CharField(max_length=20, blank=True, null=True)
    ventanilla = models.CharField(max_length=20, blank=True, null=True)
    hora_atencion = models.DateTimeField(blank=True, null=True)
    llamando = models.CharField(max_length=2, blank=True, null=True)
    fec_llamado = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'general'


class GeneralSires(models.Model):
    idgeneral = models.AutoField(primary_key=True)
    turno = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    atendido = models.CharField(max_length=2, blank=True, null=True)
    caf = models.IntegerField(blank=True, null=True)
    usuario = models.CharField(max_length=50, blank=True, null=True)
    ventanilla = models.CharField(max_length=20, blank=True, null=True)
    hora_atencion = models.DateTimeField(blank=True, null=True)
    llamando = models.CharField(max_length=2, blank=True, null=True)
    consultorio = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'general_sires'


class Magisterio(models.Model):
    turno = models.CharField(max_length=10, blank=True, null=True)
    numero = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    atendido = models.CharField(max_length=2, blank=True, null=True)
    caf = models.IntegerField(blank=True, null=True)
    usuario = models.CharField(max_length=20, blank=True, null=True)
    ventanilla = models.CharField(max_length=20, blank=True, null=True)
    hora_atencion = models.DateTimeField(blank=True, null=True)
    llamando = models.CharField(max_length=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'magisterio'


class ParticularSires(models.Model):
    idparticular = models.AutoField(primary_key=True)
    turno = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    atendido = models.CharField(max_length=2, blank=True, null=True)
    caf = models.IntegerField(blank=True, null=True)
    usuario = models.CharField(max_length=50, blank=True, null=True)
    ventanilla = models.CharField(max_length=20, blank=True, null=True)
    hora_atencion = models.DateTimeField(blank=True, null=True)
    llamando = models.CharField(max_length=2, blank=True, null=True)
    consultorio = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'particular_sires'


class Pendiente(models.Model):
    idpreferencial = models.AutoField(primary_key=True)
    turno = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    atendido = models.CharField(max_length=2, blank=True, null=True)
    caf = models.IntegerField(blank=True, null=True)
    usuario = models.CharField(max_length=50, blank=True, null=True)
    ventanilla = models.CharField(max_length=20, blank=True, null=True)
    hora_atencion = models.DateTimeField(blank=True, null=True)
    llamando = models.CharField(max_length=2, blank=True, null=True)
    fec_llamado = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pendiente'


class Personas(models.Model):
    documento = models.TextField(blank=True, null=True)
    nombre = models.TextField(blank=True, null=True)
    apellido = models.TextField(blank=True, null=True)
    pais = models.TextField(blank=True, null=True)
    visa = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'personas'


class Preferencial(models.Model):
    idpreferencial = models.AutoField(primary_key=True)
    turno = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    atendido = models.CharField(max_length=2, blank=True, null=True)
    caf = models.IntegerField(blank=True, null=True)
    usuario = models.CharField(max_length=20, blank=True, null=True)
    ventanilla = models.CharField(max_length=20, blank=True, null=True)
    hora_atencion = models.DateTimeField(blank=True, null=True)
    llamando = models.CharField(max_length=2, blank=True, null=True)
    fec_llamado = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'preferencial'


class PreferencialSires(models.Model):
    idpreferencial = models.AutoField(primary_key=True)
    turno = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    atendido = models.CharField(max_length=2, blank=True, null=True)
    caf = models.IntegerField(blank=True, null=True)
    usuario = models.CharField(max_length=50, blank=True, null=True)
    ventanilla = models.CharField(max_length=20, blank=True, null=True)
    hora_atencion = models.DateTimeField(blank=True, null=True)
    llamando = models.CharField(max_length=2, blank=True, null=True)
    consultorio = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'preferencial_sires'


class Rotulos(models.Model):
    disp = models.IntegerField(blank=True, null=True)
    empresa = models.CharField(max_length=30, blank=True, null=True)
    numcaja = models.IntegerField(blank=True, null=True)
    guias = models.CharField(max_length=50, blank=True, null=True)
    remision = models.IntegerField(blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    hora = models.TimeField(blank=True, null=True)
    estado = models.CharField(max_length=20, blank=True, null=True)
    transportadora = models.CharField(max_length=30, blank=True, null=True)
    disp2 = models.IntegerField(blank=True, null=True)
    tentr = models.IntegerField(blank=True, null=True)
    correodisp = models.CharField(max_length=50, blank=True, null=True)
    correocoor = models.CharField(max_length=50, blank=True, null=True)
    medicar = models.CharField(max_length=10, blank=True, null=True)
    usuario = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'rotulos'


class Usuario(models.Model):
    usuario = models.CharField(max_length=30, blank=True, null=True)
    clave = models.CharField(max_length=30, blank=True, null=True)
    tipo_documento = models.CharField(max_length=30, blank=True, null=True)
    documento = models.CharField(max_length=30, blank=True, null=True)
    nombre_completo = models.CharField(max_length=50, blank=True, null=True)
    primer_nombre = models.CharField(max_length=30, blank=True, null=True)
    segundo_nombre = models.CharField(max_length=30, blank=True, null=True)
    primer_apellido = models.CharField(max_length=30, blank=True, null=True)
    segundo_apellido = models.CharField(max_length=30, blank=True, null=True)
    celular = models.CharField(max_length=30, blank=True, null=True)
    email = models.CharField(max_length=40, blank=True, null=True)
    estado = models.CharField(max_length=20, blank=True, null=True)
    centro_asignado = models.CharField(max_length=10, blank=True, null=True)
    cargo = models.CharField(max_length=40, blank=True, null=True)
    fecha_creación = models.DateField(blank=True, null=True)
    en_linea = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usuario'


class UsuarioSires(models.Model):
    usuario = models.CharField(max_length=50)
    clave = models.CharField(max_length=50)
    tipo_documento = models.CharField(max_length=50)
    documento = models.CharField(max_length=20)
    nombre_completo = models.CharField(max_length=100)
    primer_nombre = models.CharField(max_length=50)
    segundo_nombre = models.CharField(max_length=50, blank=True, null=True)
    primer_apellido = models.CharField(max_length=50)
    segundo_apellido = models.CharField(max_length=50, blank=True, null=True)
    celular = models.CharField(max_length=20)
    email = models.CharField(max_length=100)
    estado = models.CharField(max_length=30, blank=True, null=True)
    centro_asignado = models.CharField(max_length=50)
    cargo = models.CharField(max_length=50)
    fecha_creación = models.DateField()

    class Meta:
        managed = False
        db_table = 'usuario_sires'


class MutualserManager(models.Manager):
    def get_by_doc(self, tipo, doc):
        return self.filter(documento=doc, tipo_documento=tipo).first()


class Mutualser(models.Model):
    documento = models.CharField(max_length=32, db_index=True, primary_key=True)
    tipo_documento = models.CharField(max_length=10, db_index=True)
    nombres = models.CharField(max_length=150, blank=True, null=True)
    apellido = models.CharField(max_length=150, blank=True, null=True)
    sexo = models.CharField(max_length=1, blank=True, null=True)  # e.g., 'M' or 'F'
    fecha_nacimiento = models.DateField(blank=True, null=True)
    departamento = models.CharField(max_length=100, blank=True, null=True)
    municipio = models.CharField(max_length=100, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    tipo_beneficiario = models.CharField(max_length=50, blank=True, null=True)
    codigo_ips = models.PositiveIntegerField(blank=True, null=True)
    categoria = models.PositiveSmallIntegerField(blank=True, null=True)

    objects = MutualserManager()

    class Meta:
        managed = False
        db_table = 'mutualser'
        unique_together = [('documento', 'tipo_documento')]
        indexes = [
            models.Index(fields=['documento', 'tipo_documento'], name='idx_doc_tipo'),
        ]

    @classmethod
    def get_afiliado_by_doc(cls, tipo_documento, documento):
        """Busca un afiliado en tabla mutualser con base en tipo_documento y documento"""
        if instance := cls.objects.get_by_doc(tipo_documento, documento):
            logger.info(f'Afiliado {tipo_documento}{documento} buscado y encontrado en BD '
                        f'por que en API mutualser no hubo resultados.')
            return {
                'NOMBRE': instance.nombres,
                'PRIMER_NOMBRE': instance.nombres.split(' ')[0],
                'APELLIDO': instance.apellido,
                'PRIMER_APELLIDO': '',
                'status': 'ACTIVO'
            }
        logger.warning(f'Afiliado {tipo_documento}{documento} buscado y NO ENCONTRADO en BD '
                       f'por que en API mutualser no hubo resultados.')
        return {}
