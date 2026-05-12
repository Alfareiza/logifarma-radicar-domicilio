import re

from core.apps.base.resources.api_calls import call_api_medicar
from core.settings import logger as log
from pydantic import BaseModel, ConfigDict, RootModel, field_validator


def obtener_datos_formula(num_aut: int, nit: str = '901543211') -> dict:
    """
    Recibe el número de autorización que aparece en los pedidos de
    los usuarios, luego el llamado a la API y retorna un diccionário
    con la respuesta.
    :param num_aut: Número de autorización a ser consultada.
               Ej.: 5022600074146
   :return: Diccionário con la respuesta de la API:
            Ej: En caso de haber un error
                {}
            Ej: En caso de no haber encontrado registros
                { "error": "No se han encontrado registros."}
            Ej: En caso de enviar el nit incorrecto
                { "error": "El Nit ingresado no corresponde a ningun convenio."}
            Ej: En caso de haber encontrado registros
                {
                    "ssc": 2640835,
                    "autorizacion": "875800731698",
                    "factura": null,
                    "fecha_de_factura": null,
                    "hora_de_factura": null,
                    "resolucion_de_factura": null,
                    "codigo_centro_factura": "920",
                    "nombre_centro_factura": "Central Domicilios Barranquilla (920)",
                    "direccion_centro_factura": "VIA 40 No. 69 - 58 Bodega D5 Parque \r\nIndustrial VIA 40",
                    "usuario_dispensa": "Silva Jose Thiago Camargo",
                    "nombre_eps": "CAJA DE COMPENSACION FAMILIAR CAJACOPI ATLANTICO",
                    "nit_eps": "890102044",
                    "plan": "REGIMEN SUBSIDIADO",
                    "direccion_eps": "Calle 4 No 4 – 5",
                    "nombre_afiliado": "GUTIERREZ TEIXEIRA JACKSON WOH",
                    "tipo_documento_afiliado": "CC",
                    "documento_afiliado": "12340316",
                    "nivel": "6",
                    "mipres": null,
                    "id_mipres": null,
                    "nombre_medico": "FRANK LAMPARD",
                    "nombre_ips": "Hospital De Leticia Materno Infantil",
                    "articulos": [
                        {
                            "codigo_barras": "7707184601001",
                            "cum": "20089927-1",
                            "atc": "J01XX01",
                            "descripcion": "FOSFOMICINA 3G POL ORL C*1 SOB X 8G (LESGENA) - CLOSTER PHARMA",
                            "cantidad": 0,
                            "costo_promedio": 0,
                            "precio_venta": null,
                            "iva": 0
                        },
                        {
                            "codigo_barras": "7703454121620",
                            "cum": "19982964-5",
                            "atc": "B03AE02",
                            "descripcion": "HERREX FOL 1000 X 30  TABLETAS",
                            "cantidad": 0,
                            "costo_promedio": 0,
                            "precio_venta": null,
                            "iva": 0
                        }
                    ]
                }
    """
    resp = call_api_medicar(
        {"nit_eps": nit, "autorizacion": f"{num_aut}"},
        'logifarma/obtenerDatosFormula'
    )
    try:
        if isinstance(resp, list) and len(resp) == 1 and 'autorizacion' in resp[0].keys():
            resp = resp[0]
    except KeyError:
        log.error("Al consultarse \'obtenerDatosFormula\' hubo una respuesta inesperada: ", str(resp))
        return {}
    return resp


def obtener_inventario(centro: int) -> list[dict]:
    """
    Consulta el inventario a partir de un 'Centro'
    :param centro: Número de bodega a ser consultada (centro).
    :return: Lista de diccionários donde cada uno representa
             un articulo con informacion relacionada a el.
             Se asume que si el artículo se encuentra en la lista
             es porque hay inventario de este.
             Ex.:
             Si no hubo problemas con la API la respuesta podría ser así:
                [
                    {
                      'Centro': '920',
                      'CodMol': 13498,
                      'CodBarra': '77012345667',
                      'Descripcion': 'Nombre del articulo',
                      'Lote': '23A634',
                      'FechaVencimiento': '2033-04-30',
                      'Inventario': 12,
                      'CostoPromedio': 3456,
                      'CantidadEmpaque': 78
                    }
                    ...
                ]
            Si hubo problemas con la API la respuesta podría ser así:
            - {'error': 'No se han encontrado registros.', 'codigo': '1'}
            - {}

    """
    resp = call_api_medicar({'Centro': centro}, 'list-inventory/client/6')
    if isinstance(resp, list):
        return resp
    return []

def obtener_historico_dispensados_usuario(documento: str, dias_dispensacion: int = 25) -> list:
    """Busca el histórico de dispensados para un determinado usuario en los ultimos 25 días."""
    return call_api_medicar({
        "NumeroDocumento": documento,
        "DiasDispensacion": dias_dispensacion,
        "PendientesActivos": True,
        "IdConvenio": 0
    }, 'historico-dispensaciones/client/6')


CodMolType = int | str


class HistoricoDispensacionItem(BaseModel):
    """One dispensación line inside Articulos[].Dispensaciones[]."""

    model_config = ConfigDict(extra="ignore")

    CantidadDispensada: int | float = 0
    FecDisp: str | None = None

    @field_validator("CantidadDispensada", mode="before")
    @classmethod
    def coerce_cantidad(cls, v: object) -> int | float:
        if v is None:
            return 0
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int | float):
            return v
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            return 0


class HistoricoArticuloMedicar(BaseModel):
    """Articulo node under SSCs[].Articulos[]."""

    model_config = ConfigDict(extra="ignore")

    CodMol: CodMolType
    Plu: str | None = None
    Descripcion: str | None = None
    CantidadSolicitada: int | float | None = None
    CantidadPendiente: int | float | None = None
    InventarioMoleculaCentro: int | float | None = None
    TotalPendienteMoleculaCentro: int | float | None = None
    TransitoMoleculaCentro: int | float | None = None
    Dispensaciones: list[HistoricoDispensacionItem] = []


class HistoricoSSCMedicar(BaseModel):
    """SSC node under top-level SSCs[]."""

    model_config = ConfigDict(extra="ignore")

    SSC: int | None = None
    SubPlan: str | None = None
    Autorizacion: str | None = None
    MIPRES: str | None = None
    FecSol: str | None = None
    Centro: str | None = None
    NombCaf: str | None = None
    Articulos: list[HistoricoArticuloMedicar] = []


class HistoricoDispensado(BaseModel):
    """
    One affiliate record from historico-dispensaciones (Medicar).

    Use ``HistoricoDispensado(**resp)`` when ``resp`` is a single dict from the API list.
    """

    model_config = ConfigDict(extra="ignore")

    TipoDoc: str | None = None
    NumeroDocumento: str | None = None
    Afiliado: str | None = None
    PendientesActivos: bool | None = None
    SSCs: list[HistoricoSSCMedicar] = []

    def sum_cantidad_dispensada_por_cod_mol(self, cod_mol: CodMolType) -> int:
        """Sum CantidadDispensada for this afiliado row, all SSCs/articulos matching CodMol."""
        return sum_cantidad_dispensada_cod_mol_afiliado(self, cod_mol)


class HistoricoDispensados(RootModel[list[HistoricoDispensado]]):
    """
    Validates the full Medicar list response.

    ``HistoricoDispensados.model_validate(raw_list)`` when ``raw_list`` is the API body.
    """

    root: list[HistoricoDispensado]

    def sum_cantidad_dispensada_por_cod_mol(self, cod_mol: CodMolType) -> int:
        """Sum CantidadDispensada across all afiliado records for the given CodMol."""
        return sum(
            rec.sum_cantidad_dispensada_por_cod_mol(cod_mol) for rec in self.root
        )

    def model_dump_list(self) -> list[dict]:
        """Serialize back to plain dicts with Medicar-like keys for API consumers."""
        return [r.model_dump(mode="json") for r in self.root]


def _cod_mol_equals(a: CodMolType, b: CodMolType) -> bool:
    return str(a).strip() == str(b).strip()


def sum_cantidad_dispensada_cod_mol_afiliado(
    afiliado: HistoricoDispensado, cod_mol: CodMolType
) -> int:
    total = 0
    for ssc in afiliado.SSCs:
        for art in ssc.Articulos:
            if not _cod_mol_equals(art.CodMol, cod_mol):
                continue
            for disp in art.Dispensaciones:
                try:
                    total += int(float(disp.CantidadDispensada))
                except (TypeError, ValueError):
                    continue
    return total


def validate_historico_dispensados(raw: object) -> HistoricoDispensados:
    """
    Parse Medicar historico-dispensaciones response.

    :raises TypeError: if ``raw`` is not a list.
    :raises pydantic.ValidationError: if list items do not match the schema.
    """
    if not isinstance(raw, list):
        msg = f"La respuesta de historico dispensaciones debe ser una lista; se recibió {raw}"
        raise TypeError(msg)
    return HistoricoDispensados.model_validate(raw)


class EpsSchema(BaseModel):
    nitEps: str

class AfiliadoSchema(BaseModel):
    tipo_documento: str
    numero_documento: str

class DosisSchema(BaseModel):
    tomar: int
    cada: int
    unidad_cada: str
    durante: int
    unidad_durante: str

    @classmethod
    def from_articulo(cls, articulo: "Articulo")-> "DosisSchema":
        return cls.from_dict(articulo.__dict__)

    @classmethod
    def from_dict(cls, data: dict) -> "DosisSchema":
        """
        Convierte un diccionario de datos de un articulo en un objeto DosisSchema.
        Ejemplo de diccionario:
        {
            "Via": "Oral",
            "Dosis": "1 UND",
            "Nombre": "METOPROLOL SUCCINATO 50mg",
            "Numero": 1,
            "Cantidad": {
                "Formulada": {
                "Valor": 90,
                "Descripcion": null
                },
                "Dispensada": {
                "Valor": 30,
                "Descripcion": "Por mes"
                }
            },
            "Duracion": {
                "Valor": 3,
                "Unidad": "Meses"
            },
            "Frecuencia": "Cada 24 horas",
            "Indicaciones": "Ninguno",
            "Concentracion": "50mg",
            "PrincipioActivo": "Metoprolol Succinato",
            "FormaFarmaceutica": ""
        }
        :param data: Diccionario de datos del articulo.
        :return: Objeto DosisSchema.
        """
        # 1. Extract 'tomar' from "Dosis" (e.g., "1 AMP" -> 1)
        dosis_text = data.get("Dosis", "0")
        tomar_match = re.search(r"(\d+)", str(dosis_text))
        tomar = int(tomar_match.group(1)) if tomar_match else 0

        # 2. Extract 'cada' and 'unidad_cada' from "Frecuencia"
        frecuencia = data.get("Frecuencia", "").strip()
        cada = 1  # Default
        unidad_cada = "unica"

        # Regex Patterns
        patterns = [
            # Style: "Cada 4 horas" or "Cada 12 horas"
            (r"(?i)cada\s+(?P<val>\d+)\s+(?P<unit>\w+)", lambda m: (int(m.group("val")), m.group("unit"))),
            # Style: "Cada noche" or "Cada día"
            (r"(?i)cada\s+(?P<unit>\w+)", lambda m: (1, m.group("unit"))),
            # Style: "Dosis unica"
            (r"(?i)dosis\s+unica", lambda m: (1, "unica")),
        ]

        for pattern, handler in patterns:
            match = re.search(pattern, frecuencia)
            if match:
                cada, unidad_cada = handler(match)
                break

        # 3. Extract 'durante' and 'unidad_durante'
        valor, unidad = data.get("Duracion").Valor, data.get("Duracion").Unidad
        
        return cls(
            tomar=tomar,
            cada=cada,
            unidad_cada=unidad_cada,
            durante=valor,
            unidad_durante=unidad
        )

class MedicamentoSchema(BaseModel):
    plu: str
    articulo: str
    dosis: DosisSchema
    cantidad_formulada: int
    cantidad_dispensada: int

class FormulaDetailsSchema(BaseModel):
    plan: str
    subplan: str
    fecha_formula: str  # We can validate this format later
    medico_formulador: dict  # Or define a specific schema
    diagnostico: str
    medicamentos: list[MedicamentoSchema]

class MedicarFormulaSchema(BaseModel):
    """Este modelo es usado para crear el payload de la API de Medicar para la creación de una formula medica."""
    eps: EpsSchema
    nit_ips: str | None
    nombre_ips: str
    tipo_formula: str
    afiliado: AfiliadoSchema
    formula: FormulaDetailsSchema

    @field_validator("nit_ips", mode="before")
    @classmethod
    def clean_strings(cls, v):
        return v.strip() if isinstance(v, str) else v

    @classmethod
    def from_radicado(cls, radicado: 'Radicacion') -> "MedicarFormulaSchema":
        """
        Builds the schema from a 'Radicacion' instance.
        Assumes the latest transaction (even if discard=True).
        """
        # Get the latest OCR Transaction
        ocr_txn = radicado.prescription_ocr_transactions.latest('created_at')
        # 2. This is now a PrescriptionOCRResult object with full type hinting
        result: 'PrescriptionOCRResult' = ocr_txn.ocr_result

        # 2. OPTIMIZATION: Fetch all barra transactions in ONE query.
        # We use select_related('article_sap') to JOIN the SAP table immediately.
        # We order by 'created_at' so that the latest one overwrites in the dict.
        barras_queryset = ocr_txn.barra_transactions.select_related('article_sap').order_by('created_at')

        # Create a lookup map: { 'article_nombre': search_barra_object }
        barras_map = {b.article_nombre: b for b in barras_queryset}

        return cls(
            eps=EpsSchema(nitEps=radicado.nit_convenio),
            nit_ips=result.NitIPS or "1111111111",
            nombre_ips=result.IPS,
            tipo_formula="Ambulatoria",
            afiliado=AfiliadoSchema(
                tipo_documento=radicado.tipo_documento_paciente,
                numero_documento=radicado.numero_documento_paciente
            ),
            formula=FormulaDetailsSchema(
                plan='',
                subplan='',
                fecha_formula=f"{result.FechaFormula:%Y%m%d}",
                medico_formulador={"nombre": result.NombreMedico},
                diagnostico=result.diagnostico_principal,
                medicamentos=[
                    cls._build_medicamento(art, barras_map.get(art.Nombre))
                    for art in result.Articulos
                ]
            )
        )
    
    @staticmethod
    def _build_medicamento(art: 'Articulo', barra_txn: 'SearchBarra'):
        """Helper to build MedicamentoSchema avoiding NoneType errors."""
        # Fallbacks if the barra search failed or doesn't exist
        descripcion = (
            barra_txn.article_sap.descripcion 
            if barra_txn and barra_txn.article_sap 
            else art.Nombre
        )
        plu = barra_txn.result if barra_txn and barra_txn.result else ""
        
        return MedicamentoSchema(
            plu=plu,
            articulo=descripcion,
            dosis=DosisSchema.from_articulo(art),
            cantidad_formulada=art.Cantidad.Formulada.Valor,
            cantidad_dispensada=art.Cantidad.Dispensada.Valor
        )
