from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.apps.base.models import Barrio, Municipio, Radicacion


@extend_schema_field({'example': "2023-04-19 17:15"})
class CustomDateTimeField(serializers.DateTimeField):
    def to_representation(self, value):
        value = value.astimezone(timezone.get_current_timezone())
        value = value.strftime("%Y-%m-%d %H:%M")
        return super().to_representation(value)


class MunicipioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipio
        exclude = ['id']
        # fields = '__all__'


class BarrioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barrio
        exclude = ['id', 'cod_zona', 'status', 'municipio']
        # fields = '__all__'


class RadicacionSerializer(serializers.ModelSerializer):
    municipio = MunicipioSerializer()
    barrio = BarrioSerializer()
    datetime = CustomDateTimeField()

    class Meta:
        model = Radicacion
        fields = [
            'datetime', 'numero_radicado', 'municipio', 'barrio', 'cel_uno',
            'cel_dos', 'email', 'direccion', 'paciente_nombre', 'paciente_cc',
            'estado', 'acta_entrega'
        ]


class RadicacionDetailSerializer(RadicacionSerializer):
    alistamiento = CustomDateTimeField()
    despachado = CustomDateTimeField()

    class Meta(RadicacionSerializer.Meta):
        fields = RadicacionSerializer.Meta.fields + ['ip', 'paciente_data',
                                                     'domiciliario_nombre',
                                                     'domiciliario_ide',
                                                     'domiciliario_empresa',
                                                     'alistamiento',
                                                     'alistado_por',
                                                     'despachado',
                                                     'factura']


class RadicacionWriteSerializer(serializers.ModelSerializer):
    barrio_id = serializers.IntegerField()
    municipio_id = serializers.IntegerField()

    class Meta(RadicacionSerializer.Meta):
        model = Radicacion
        fields = [
            'numero_radicado', 'cel_uno', 'ip', 'paciente_data',
            'cel_dos', 'email', 'direccion', 'barrio_id', 'municipio_id',
            'paciente_nombre', 'paciente_cc'
        ]


class RadicacionPartialUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Radicacion
        fields = [
            'acta_entrega', 'estado', 'domiciliario_nombre',
            'domiciliario_ide', 'domiciliario_empresa',
            'alistamiento', 'alistado_por',
            'despachado', 'factura'
        ]
