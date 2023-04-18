from datetime import datetime, timedelta

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .serializers import RadicacionDetailSerializer, \
    RadicacionPartialUpdateSerializer, RadicacionSerializer, \
    RadicacionWriteSerializer
from ..base.models import Barrio, Municipio, Radicacion


@extend_schema_view(
    list=extend_schema(
        summary="Lista los radicados.",
        description="Lista todos los radicados en los últimos 7 días.",
    ),
    retrieve=extend_schema(
        summary="Información de un radicado.",
        description="Información en detalle de una radicación.",
    ),
    create=extend_schema(
        summary='Crea un radicado.',
        description='Crea un radicado con base en la información recibida.',
        responses=RadicacionDetailSerializer
    ),
    partial_update=extend_schema(
        summary="Edita un radicado.",
        description="Edita un radicado con base a la información recibida.",
        responses=RadicacionDetailSerializer
    )
)
class RadicacionViewSet(viewsets.ModelViewSet):
    serializer_class = RadicacionDetailSerializer
    pagination_class = PageNumberPagination
    http_method_names = ["get", "post", "patch"]
    pagination_class.page_size = 10
    lookup_field = 'numero_radicado'

    def get_paginated_response(self, data):
        return self.paginator.get_paginated_response(data)

    def get_queryset(self):
        """Filter the last 7 days of Radicacion objects"""
        end, start = create_range_dates()
        return Radicacion.objects.filter(
            datetime__range=[start, end]
        ).order_by('-datetime')

    def get_serializer_class(self):
        """Return the serializer class for the request"""
        if self.action == "list":
            return RadicacionSerializer
        if self.action == "create":
            return RadicacionWriteSerializer
        if self.action == "partial_update":
            return RadicacionPartialUpdateSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        """Crea una radicación"""
        params = {'ip': request.META.get('HTTP_X_FORWARDED_FOR',
                                         request.META.get('REMOTE_ADDR'))}

        if 'paciente_nombre':
            request.data['paciente_nombre'].upper()

        if 'paciente_data' not in request.data:
            params.update(paciente_data='')

        if 'barrio_id' in request.data:
            barr = Barrio.objects.filter(id=request.data['barrio_id']).first()
            if not barr:
                raise Barrio.DoesNotExist
            else:
                params.update(barrio_id=barr.id)

        if 'municipio_id' in request.data:
            mun = Municipio.objects.filter(
                id=request.data['municipio_id']).first()
            if not mun:
                raise Municipio.DoesNotExist
            else:
                params.update(municipio_id=mun.id)

        request.data.update(params)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        response_serializer = RadicacionDetailSerializer(
            instance=serializer.instance
        )
        return Response(response_serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)

    def update(self, request, *args, **kwargs):
        """
        Permite que sean actualizados uno o más campos de un radicado existente.
        :param request:
                   Ex.: <rest_framework.request.Request: PATCH '/api/v1/radicaciones/8881122112/'>
               request.data:
                Ex.: {'paciente_cc': '0'}
        :param args:
               Ex.: ()
        :param kwargs:
                  Ex.:{'numero_radicado': '8881122112', 'partial': True}
        :return: En caso de haber realizado el cambio con éxito retorna
        el detalle del radicado basado en el schema RadicacionDetailSerializer.
        Caso contrario retorna un json informando los campos inválidos con un
        status_code de 400.
        """
        instance = self.get_object()
        serializer = self.get_serializer()
        fields_to_update = request.data.keys()

        # Avoiding unchangeable fields
        invalid_fields = set(fields_to_update) - set(serializer.fields)
        if invalid_fields:
            return Response(
                {"Invalid fields": ", ".join(invalid_fields)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # DateTimeFields
        datetime_fields = set(fields_to_update).intersection(
            ['alistamiento', 'despachado'])
        if datetime_fields:
            for field in datetime_fields:
                try:
                    request.data[field] = datetime.strptime(
                        request.data[field], "%Y-%m-%d %H:%M"
                    )
                except Exception as e:
                    return Response(
                        {"Invalid format date": str(e)},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        # Proceed to update the object
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data,
                                         partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        response_serializer = RadicacionDetailSerializer(instance)
        return Response(response_serializer.data)


def create_range_dates(days: int = 7):
    """
    Since today, generate two dates
    :param days:
    :return: Two dates where the first is n days before and the
    second is today at 23:59:59
    """
    enddate = datetime.now()
    startdate = enddate - timedelta(days=days)
    startdate = startdate.replace(hour=0, minute=0, second=0,
                                  microsecond=0)
    enddate = enddate.replace(hour=23, minute=59, second=59,
                              microsecond=0)
    return enddate, startdate
