import traceback
from datetime import timedelta
from enum import Enum
from time import sleep

from django.core.validators import MinValueValidator, MaxValueValidator
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
    DateField, TextField, FloatField, UniqueConstraint,
)
from django.db.models.fields import BigIntegerField
from django.utils import timezone
from django.utils.timezone import now
from django.contrib.auth.models import User

from core.apps.base.scrapper_requests import MutualScrapper
from core.apps.base.resources.medicar import obtener_datos_formula
from core.apps.base.resources.tools import pretty_date
from core.apps.tasks.utils.dt_utils import Timer
from core.settings import ZONA_SER_URL


class Status(str, Enum):
    """
    Status — The status of whatever is being tracked — step, entire flow, record
    """

    COMPLETED = "completado"
    """
    The item has completed successfully.
    """

    FAILED = "fallido"
    """
    The item has failed.
    """

    WARNING = "advertencia"
    """
    The item requires attention.
    """

    RUNNING = "en ejecucion"
    """
    The item is running.
    """


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
    convenio = CharField(max_length=24, blank=True, null=True)
    municipio = ForeignKey(Municipio, on_delete=CASCADE)
    barrio = ForeignKey(Barrio, on_delete=CASCADE)
    cel_uno = CharField(max_length=24, blank=True, null=True)
    cel_dos = CharField(max_length=24, blank=True, null=True)
    cel_uno_validado = BooleanField(default=False)
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

    # Uso interno loigarma
    visto = BooleanField(default=False)

    def __str__(self):
        return f"{self.numero_radicado}"

    @property
    def foto_formula(self) -> str:
        """Determina la url de la imagen de la formula, el cual es una foto tomada en su momento por el usuario"""
        if self.paciente_data and 'IMG_ID' in self.paciente_data:
            return f"https://drive.google.com/file/d/{self.paciente_data['IMG_ID']}/view"
        return ''

    @property
    def medicamento_autorizado(self) -> bool:
        """Determina si el radicado contiene medicamentos autorizados."""
        return 'FECHA_AUTORIZACION' in self.paciente_data or 'DIAGNOSTICO' in self.paciente_data

    @property
    def numero_autorizacion(self):
        if 'mutual' in self.convenio:
            return self.numero_radicado
        return self.numero_radicado if self.medicamento_autorizado else f"F{self.id}"

    @property
    def is_anulado(self):
        return 'anulad' in str(self.acta_entrega).lower()


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


class ScrapMutualSer(Model):
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    duracion = FloatField(null=True)
    tipo_documento = CharField(max_length=20, null=True, blank=True)
    documento = CharField(max_length=30, null=True, blank=True)
    texto_error = TextField()
    estado = CharField(max_length=50, null=True, blank=True)
    resultado = JSONField(blank=True, null=True)
    tipo = CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        if self.resultado_con_datos:
            return f"Scrap de {self.tipo_documento}{self.documento} | Autorizaciones ({self.qty_auts}: {', '.join([i['NUMERO_AUTORIZACION'] for i in self.resultado])}"
        return f"Scrap de {self.tipo_documento}{self.documento}"

    class Meta:
        db_table = 'base_scrapper'

    @property
    def is_cache(self) -> bool:
        return 'cache' in self.tipo if self.tipo else False

    @property
    def aut_pendientes_por_disp_groub_by_nro_aut(self) -> dict:
        """Create a dict where the key is the NUMERO_AUTORIZACION and the value is a list with 'DETALLE_AUTORIZACION'"""
        return {aut['NUMERO_AUTORIZACION']: aut['DETALLE_AUTORIZACION']
                for aut in self.resultado
                if aut['DISPENSADO'] not in (None, True)}

    @property
    def aut_dispensadas_groub_by_nro_para_facturar(self) -> dict:
        """Create a dict where the key is the NUMERO_AUTORIZACION and the value is a list with 'DETALLE_AUTORIZACION'"""
        return {aut['NUMERO_AUTORIZACION']: aut
                for aut in self.resultado
                if aut['DISPENSADO']}

    @property
    def resultado_con_datos(self) -> bool:
        """Determina si el scrapper fue realizado y retornó resultados."""
        return self.texto_error == '' and isinstance(self.resultado, list) and self.resultado

    @property
    def qty_auts(self) -> int:
        return len(self.resultado) if self.resultado_con_datos else 0

    def get_info_user_from_zona_ser(self):
        """Inicializa el processo de scrapping en mutual ser"""
        self.tipo = 'busca autorizaciones de usuario'
        self.estado = Status.RUNNING
        self.save()

        try:
            # scrapper = MutualSerPage()
            # result = scrapper.find_user(self.tipo_documento, self.documento)
            scrapper = MutualScrapper(self.tipo_documento, self.documento)
            result = scrapper.find_user()
        except Exception:
            self.texto_error = traceback.format_exc()
            self.estado = Status.FAILED
        else:
            if 'MSG' in result:
                self.texto_error = result['MSG'].replace("\"", '')
            self.resultado = result
            self.estado = Status.COMPLETED
        finally:
            self.duracion = (now() - self.created_at).total_seconds()
            self.save()

    @classmethod
    def get_scrap_last_minutes(cls, _id, tipo_documento, documento, minutes):
        """Revisa los scrappers completados de un tipo de documento con documento en los ultimos minutos."""
        minutos_atras = now() - timedelta(minutes=minutes)
        if scrap := ScrapMutualSer.objects.filter(
                tipo_documento=tipo_documento,
                documento=documento,
                estado='completado',
                updated_at__gte=minutos_atras
        ).exclude(id=_id):
            return scrap.last()
        return None

    def create_or_get_and_scrap(self):
        """Gestiona como una fila la creación de scrapping."""
        if scrap := self.get_scrap_last_minutes(self.id, self.tipo_documento, self.documento, 30):
            return self.duplicate_attrs_from_existing(scrap)
        timer = Timer(15)
        while timer.not_expired:
            latest_scraps = ScrapMutualSer.objects.order_by('-created_at').values_list('id', flat=True)[:5]
            # Si al menos uno de los últimos 1 scrappings terminó
            if ScrapMutualSer.objects.filter(id__in=latest_scraps).exclude(estado=Status.RUNNING).exists():
                self.get_info_user_from_zona_ser()
                return
            sleep(0.5)

        raise TimeoutError("Tenemos nuestro sistema ocupado, intenta más tarde.")

    def duplicate_attrs_from_existing(self, scrap):
        self.tipo = f"cache de id # {scrap.id}"
        self.resultado = scrap.resultado
        self.estado = scrap.estado
        self.duracion = (self.updated_at - self.created_at).total_seconds()
        self.save()
        return

    def load_dispensado_in_resultado(self):
        """Busca cada autorización presente en resultado en Medicar y llena la variable 'DISPENSADO' con un buleano
        que determina si fue dispensado o no. En caso no encontrarla en Medicar, busca en Radicacion.
        """

        def aut_exists(nro_aut) -> bool:
            return Radicacion.objects.filter(
                numero_radicado=nro_aut,
                acta_entrega__isnull=True, convenio='mutualser',
                paciente_cc=f"{self.tipo_documento}{self.documento}",
            ).only('id', 'datetime')

        for autorizacion in self.resultado:
            # TODO revisar posibles respuestas de API para garantizar información correcta en 'DISPENSADO'
            # if 'cache' in self.tipo:
            #     continue
            resp_mcar = obtener_datos_formula(autorizacion['NUMERO_AUTORIZACION'], '806008394')
            # Si trae resultados de medicar, entonces se asume que fue dispensado
            autorizacion['DISPENSADO'] = resp_mcar != {"error": "No se han encontrado registros."}
            if not autorizacion['DISPENSADO']:
                if aut := aut_exists(autorizacion['NUMERO_AUTORIZACION']):
                    autorizacion['DISPENSADO'] = True
                    autorizacion['ESTADO'] = '(En Proceso)'
                    autorizacion['RADICADO_AT'] = pretty_date(
                        aut.first().datetime.astimezone(timezone.get_current_timezone())
                    )
            else:
                autorizacion['ESTADO'] = 'Radicada'
                autorizacion['RADICADO_AT'] = ''

            self.save()


class CelularesRestringidos(Model):
    created_at = DateTimeField(auto_now_add=True)
    numero = BigIntegerField(db_index=True, primary_key=True,
                             validators=[MinValueValidator(3000000000), MaxValueValidator(3259999999)])
    registrado_por = ForeignKey(User, on_delete=CASCADE, null=True, blank=True)
    motivo = CharField(max_length=120, blank=True, null=True)

    def __str__(self):
        return f'<Cel Restringido : {self.numero}>'

    class Meta:
        db_table = 'base_celulares_restringidos'

    def save(self, *args, **kwargs):
        self.motivo = self.motivo.lower() if self.motivo else None
        return super(CelularesRestringidos, self).save(*args, **kwargs)


class OtpSMS(Model):
    created_at = DateTimeField(auto_now_add=True)
    numero = BigIntegerField(db_index=True, validators=[MinValueValidator(3000000000), MaxValueValidator(3259999999)])
    otp_code = IntegerField(blank=True, null=True)


class UsuariosRestringidos(Model):
    created_at = DateTimeField(auto_now_add=True)
    tipo_documento = CharField(max_length=20, null=True, blank=True)
    documento = CharField(max_length=30, null=True, blank=True)
    registrado_por = ForeignKey(User, on_delete=CASCADE, null=True, blank=True)
    motivo = CharField(max_length=120, blank=True, null=True)

    def __str__(self):
        return f'<Usuario Restringido : {self.tipo_documento}{self.documento}>'

    class Meta:
        db_table = "base_usuarios_restringidos"
        constraints = [
            UniqueConstraint(
                fields=["tipo_documento", "documento"],
                name="unique_tipo_documento_documento",
            ),
        ]

    def save(self, *args, **kwargs):
        self.motivo = self.motivo.lower() if self.motivo else None
        return super(UsuariosRestringidos, self).save(*args, **kwargs)