from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.apps.base.models import Barrio, Municipio, SearchBarra, Radicacion, SAPArticle
from core.apps.base.exceptions import DriveFileIdNormalizationError
from core.apps.tasks.utils.gdrive import normalize_drive_file_id


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


class PrescriptionOCRRunSerializer(serializers.Serializer):
    """
    Validates POST payloads for `/api/v1/prescription-ocr/`.

    Normalizes ``image_url`` and/or ``drive_file_id`` to a single canonical
    ``drive_file_id_normalized``. Optionally attaches an existing ``Radicacion``
    when ``numero_radicado`` matches.
    """

    image_url = serializers.CharField(required=False, allow_blank=True, max_length=2048)
    drive_file_id = serializers.CharField(required=False, allow_blank=True, max_length=200)
    numero_radicado = serializers.CharField(required=False, allow_blank=True, max_length=24)

    def validate(self, attrs):
        """Normalize Drive id from URL/body and resolve optional radicacion link."""
        url = (attrs.get('image_url') or '').strip()
        fid_in = (attrs.get('drive_file_id') or '').strip() or None
        try:
            attrs['drive_file_id_normalized'] = normalize_drive_file_id(
                drive_file_id=fid_in,
                image_url=url or None,
            )
        except DriveFileIdNormalizationError as exc:
            raise serializers.ValidationError(exc.detail) from exc
        attrs['image_url_normalized'] = url
        nr = (attrs.get('numero_radicado') or '').strip()
        attrs['radicacion_match'] = None
        if nr:
            attrs['radicacion_match'] = Radicacion.objects.filter(numero_radicado=nr).first()
        return attrs


class PrescriptionOCRDiscardSerializer(serializers.Serializer):
    """
    Validates POST payloads for `/api/v1/prescription-ocr/discard/`.

    ``drive_file_id`` is optional: when supplied, must match the transaction row to avoid
    discarding results from mismatched clipboard/context.
    """

    transaction_id = serializers.IntegerField(min_value=1)
    drive_file_id = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate(self, attrs):
        """Normalize optional Drive id using the same rules as OCR run."""
        drive_raw = (attrs.get('drive_file_id') or '').strip()
        if drive_raw:
            try:
                attrs['drive_file_id_normalized_optional'] = normalize_drive_file_id(
                    drive_file_id=drive_raw,
                    image_url=None,
                )
            except DriveFileIdNormalizationError as exc:
                raise serializers.ValidationError(exc.detail) from exc
        else:
            attrs['drive_file_id_normalized_optional'] = None
        return attrs

class SAPArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SAPArticle
        fields = '__all__'

class SearchBarraSerializer(serializers.ModelSerializer):
    sap_article = SAPArticleSerializer(source='article_sap', read_only=True)
    barra_llm = serializers.CharField(source='article_sap.barra', default='', allow_null=True)
    ips = serializers.CharField(source='prescription_ocr_transaction.ips', read_only=True)
    cost_usd = serializers.DecimalField(max_digits=12, decimal_places=6, allow_null=True)
    cached = serializers.SerializerMethodField()

    class Meta:
        model = SearchBarra
        fields = [
            'id',
            'cached',
            'prescription_ocr_transaction_id',
            'status',
            'ips',
            'article_numero',
            'article_nombre',
            'barra_llm',
            'sap_article',
            'error_message',
            'input_tokens',
            'output_tokens',
            'cache_read_input_tokens',
            'cost_usd',
        ]

    def _result(self, obj) -> dict:
        result = obj.result
        return result if isinstance(result, dict) else {}

    def get_cached(self, obj) -> bool:
        return self.context.get('cached', False)
        
