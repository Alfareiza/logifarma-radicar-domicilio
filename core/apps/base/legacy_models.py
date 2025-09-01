# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models

from core.settings import logger


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
