import traceback
from collections import namedtuple
from datetime import datetime
from pprint import pprint

import requests
from bs4 import BeautifulSoup, GuessedAtParserWarning, XMLParsedAsHTMLWarning
import re
from typing import Dict, Optional
import logging

from decorator import contextmanager
from retry import retry

from core.apps.base.exceptions import NroAutorizacionNoEncontrado, PasoNoProcesado, NoRecordsInTable, \
    RestartScrapper, SinAutorizacionesPorRadicar
import warnings

from core.apps.base.resources.tools import add_user_id_to_formatter
from core.settings import ZONA_SER_URL
from core.settings import ch, logger as log

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)


def parse_xml(response):
    try:
        Row = namedtuple('Row', ['lupa_id', 'ver_id', 'buscar_aut'])
        id_rows = []
        soup = BeautifulSoup(response)
        ele = soup.select_one('update[id="main:a3tabladesolicuti"]')
        rows = ele.find('table').find('tbody').find_all('tr', recursive=False)
    except Exception:
        log.error(msg := 'No se pudo parsear la tabla con la información de las autorizaciones')
        raise Exception(msg)
    else:
        for row in rows:
            estado = row.contents[7].find_all("option", selected=True)[-1].text
            if estado.upper() != 'APROBADO':
                continue
            cols = row.find_all('td', recursive=False)
            last_column = cols[-1]
            lupa = last_column.find_all('a')[0].get('id')  # Revisar id para lupa e id para ver
            ver = last_column.find_all('a')[-1].get('id')  # Revisar id para lupa e id para ver
            # Define cuales 'consecutivos' va a buscar en documento
            if 'Número para Facturar:Ver' not in last_column.get_text(strip=True):
                log.info("Botón de 'Ver' no está presente en esta fila, buscándolo a través de la lupa")
                id_rows.append(Row(lupa, ver, True))
            # Si botón de 'Ver' está presente en fila, entonces el número de aut está en el archivo
            id_rows.append(Row(lupa, ver, False))
            # consecutivo = cols[2].text
        return id_rows


class JSFPortalScraper:
    """
    A scraper for JSF (JavaServer Faces) portal with AJAX functionality.

    This class handles the complex authentication flow and form submission
    for the mutualser.org portal, managing session cookies, ViewState tokens,
    and AJAX requests properly.
    """
    BASE_URL = ZONA_SER_URL
    LOGIN_URL = f"{BASE_URL}/ZONASER/login.xhtml"
    HOME_URL = f"{BASE_URL}/ZONASER/home.xhtml"
    IDENTIFICACIONES = {
        'CC': 'Cedula de Ciudadania',
        'CE': 'Cedula de Extranjeria',
        'TI': 'Tarjeta de Identidad',
        'RC': 'Registro Civil',
        'PA': 'Pasaporte',
        'MS': 'Menor sin Identificacion',
        'PE': 'Permiso Especial',
        'CN': 'Certificado Nacido Vivo',
        'PT': 'Permiso Temporal',
        'SC': 'Salvo Conducto',
    }

    def __init__(self, tipo_documento, documento):
        """Initialize the JSF Portal Scraper."""
        self.session = requests.Session()
        self.view_state = None
        self.session_id = None
        self.tipo_documento = tipo_documento
        self.documento = documento
        self.ref_id_link = None

        # Set up common headers that mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
            'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        })

    def _extract_view_state(self, html_content: str) -> Optional[str]:
        """Extract ViewState token from JSF page HTML.

        Args:
            html_content (str): HTML content of the page

        Returns:
            Optional[str]: ViewState token if found, None otherwise
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        if view_state_input := soup.find(
                'input', {'name': 'javax.faces.ViewState'}
        ):
            return view_state_input.get('value')

        if view_state_input := soup.find_all('update'):
            return view_state_input[-1].text

        if view_state_match := re.search(
                r'javax\.faces\.ViewState["\']?\s*value=["\']([^"\']+)', html_content
        ):
            return view_state_match[1]

        return None

    def check_for_errors_in_ajax_response(self, response):
        """Revisa que no haya errores en respuesta AJAX."""
        if 'ui-messages-error' in response:
            log.warning("Error message detected in user type selection response")
            if error_match := re.search(
                    r'<span class="ui-messages-error-detail">([^<]+)</span>',
                    response,
            ):
                log.warning(f"Error detail: {error_match[1]}")

    def ajax_headers(self, url=None):
        """Crea un header por defecto con una url variable."""
        return {
            'Accept': 'application/xml, text/xml, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Faces-Request': 'partial/ajax',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.BASE_URL,
            'Referer': url or f"{self.BASE_URL}/ZONASER/",
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }

    def _extract_form_data(self, html_content: str, form_id: str) -> Dict[str, str]:
        """Extrae informacieon del form incluyendo campos ocultos en el formulario JSF.

        Args:
            html_content (str): Contenido HTML de la página.
            form_id (str): ID del formulario al cual se le extraerá la información.

        Returns:
            Dict[str, str]: Dictionario que contiene la información de los campos y sus valores.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        form = soup.find('form', {'id': form_id})

        if not form:
            log.warning(f"Form with ID '{form_id}' not found")
            return {}

        form_data = {}

        # Extract all input fields
        for input_field in form.find_all('input'):
            name = input_field.get('name')
            value = input_field.get('value', '')
            if name:
                form_data[name] = value

        # Extract select fields
        for select_field in form.find_all('select'):
            if name := select_field.get('name'):
                if selected_option := select_field.find('option', selected=True):
                    form_data[name] = selected_option.get('value', '')
                else:
                    form_data[name] = ''

        return form_data

    def update_view_state(self, url) -> str:
        """Accesa a la url, le extrae el viewState y returna el html."""
        response = self.session.get(url)
        response.raise_for_status()

        # Extract ViewState and session ID
        self.view_state = self._extract_view_state(response.text)
        return response.text

    def initialize_session(self):
        """Inicializa una sesión al acceder al login extrayendo el primer viewState."""
        self.update_view_state(self.LOGIN_URL)
        if not self.view_state:
            raise Exception(f'No fue posible extraer el ViewState al haber accesado a {self.LOGIN_URL}')

    def select_user_type(self, user_type: str = "Prestador"):
        """Selecciona el tipo de usuario al hacer login el cual es siempre 'Prestador'."""
        response = self.update_view_state(self.LOGIN_URL)
        form_data = self._extract_form_data(response, 'formLogin')  # Extract all current form data

        # Prepare form data for user type selection, preserving existing form state
        ajax_form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'formLogin:listBoxTipoUsuario',
            'javax.faces.partial.execute': 'formLogin:listBoxTipoUsuario',
            'javax.faces.partial.render': 'formLogin:groupNitL formLogin:groupNit',
            'javax.faces.behavior.event': 'valueChange',
            'javax.faces.partial.event': 'change',
            'formLogin': 'formLogin',
            'formLogin:listBoxTipoUsuario_input': user_type,
            'formLogin:listBoxTipoUsuario_focus': '',
            'formLogin:usuario': form_data.get('formLogin:usuario', ''),
            'formLogin:contraseña': form_data.get('formLogin:contraseña', ''),
            'javax.faces.ViewState': self.view_state
        }

        # Add any additional hidden fields found in the form
        for key, value in form_data.items():
            if key not in ajax_form_data and key.startswith('formLogin:'):
                ajax_form_data[key] = value

        response = self.session.post(
            self.LOGIN_URL,
            data=ajax_form_data,
            headers=self.ajax_headers()
        )
        response.raise_for_status()
        if new_view_state := self._extract_view_state(response.text):
            self.view_state = new_view_state
        self.check_for_errors_in_ajax_response(response.text)

    def select_consulta_solicitudes(self) -> bool:
        """Realiza el click en el botón 'Consulta Solicitudes' que se encuentra en la parte izquierda de la página."""
        self.update_view_state(self.HOME_URL)
        # Prepare form data for user type selection, preserving existing form state
        ajax_form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'main:j_idt29',
            'javax.faces.partial.execute': '@all',
            'main:j_idt29': 'main:j_idt29',
            'main:j_idt29_menuid': '0_1',
            'main': 'main',
            'javax.faces.ViewState': self.view_state
        }
        response = self.session.post(
            self.HOME_URL,
            data=ajax_form_data,
            headers=self.ajax_headers(self.HOME_URL)
        )
        response.raise_for_status()
        if new_view_state := self._extract_view_state(response.text):
            self.view_state = new_view_state
        self.check_for_errors_in_ajax_response(response.text)

    def get_ref_id(self, html, ref_id) -> str:
        """Obtiene el id de un html."""
        soup = BeautifulSoup(html, 'html')
        try:
            match ref_id:
                case 'Solicitud de autorización de servicios y tecnologías en salud':
                    resp = soup.find('div', id='main:cnsgPnlTipoConsulta_content').find(
                        'table', recursive=False).get('id')
                case 'Buscar':
                    ele = soup.find('div', id='main:cnsgPnlCentral')
                    resp = ele.find_all('div', recursive=False)[1].find_all('td')[1].find('a').get('id')
                case 'Fecha':
                    label_span = soup.find('span', string=lambda text: text and 'Fecha Prestacion Efectiva' in text)
                    value_td = label_span.find_parent('td').find_next_sibling('td')
                    target_span = value_td.find('span', id=True)
                    resp = target_span.get('id') if target_span else ''
                case 'Botón Confirmar Fecha Prest':
                    ele = soup.find('div', id='main:pnlbotones_content')
                    tds = ele.find_all('td')
                    resp = tds[0].find('button').get('id')
            if not resp:
                raise Exception
        except Exception as e:
            logging.error(msg := f"No existe opción de {ref_id}")
            raise Exception(msg) from e
        else:
            return resp

    # @retry(PasoNoProcesado, 3, 2)
    def select_solicitud_aut(self):
        """Simula el clicar en el botón 'Solicitud de autorización de servicios y tecnologías en salud'."""
        response = self.update_view_state(self.HOME_URL)
        self.ref_id_link = self.get_ref_id(response,
                                           'Solicitud de autorización de servicios y tecnologías en salud')

        # Prepare form data for user type selection, preserving existing form state
        ajax_form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': self.ref_id_link,
            'javax.faces.partial.execute': self.ref_id_link,
            'javax.faces.partial.render': 'main:cnsgPnlCentral main:messages',
            'javax.faces.behavior.event': 'valueChange',
            'javax.faces.partial.event': 'change',
            'main': 'main',
            self.ref_id_link: 'S,/pages/solicitudAut/consultasolicitudAut.xhtml',
            'javax.faces.ViewState': self.view_state
        }

        # log.info("Clicando en solicitud de autorizaciones")
        response = self.session.post(
            self.HOME_URL,
            data=ajax_form_data,
            headers=self.ajax_headers(self.HOME_URL)
        )
        response.raise_for_status()

        if 'Consecutivo del procedimiento' not in response.text:
            raise PasoNoProcesado
        # Check for errors in the AJAX response
        self.check_for_errors_in_ajax_response(response.text)
        # log.info("Solicitud de autorizaciones clicado exitosamente")

    def select_tipo_documento(self):
        """Establece el tipo de documento en el formulario."""
        response = self.update_view_state(self.HOME_URL)
        self.ref_id_link = self.get_ref_id(response,
                                           'Solicitud de autorización de servicios y tecnologías en salud')
        # Prepare form data for user type selection, preserving existing form state
        ajax_form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'main:tipoAfiliadoSolicitud',
            'javax.faces.partial.execute': 'main:tipoAfiliadoSolicitud',
            'javax.faces.behavior.event': 'change',
            'javax.faces.partial.event': 'change',
            'main': 'main',
            self.ref_id_link: 'S,/pages/solicitudAut/consultasolicitudAut.xhtml',
            'main:numeroSolicitud': '0',
            'main:aniosolicitud': '0',
            'main:fechaInicialsolicitud_input': '',
            'main:fechafinalsolicitud_input': '',
            'main:estadoSolicitud_input': ' ',
            'main:estadoSolicitud_focus': '',
            'main:tipoAfiliadoSolicitud_input': self.tipo_documento,
            'main:tipoAfiliadoSolicitud_focus': '',
            'main:documentoAfiliadoSolicitud': '',
            'main:ubicacionAfiliado_input': ' ',
            'main:ubicacionAfiliado_hinput': '',
            'main:diagnosticoPpal_input': ' ',
            'main:diagnosticoPpal_hinput': '',
            'main:udpSolicitud_input': ' ',
            'main:udpSolicitud_focus': '',
            'main:ServicioSolicitud_input': '',
            'main:ServicioSolicitud_focus': '',
            'main:a3tabladesolicuti:j_idt1398:filter': '',
            'main:a3tabladesolicuti:j_idt1407:filter': '',
            'javax.faces.ViewState': self.view_state
        }
        # log.info(f"Seleccionando tipo de documento {self.tipo_documento}")
        response = self.session.post(
            self.HOME_URL,
            data=ajax_form_data,
            headers=self.ajax_headers(self.HOME_URL)
        )
        response.raise_for_status()
        self.check_for_errors_in_ajax_response(response.text)
        # log.info("Tipo de documento seleccionado exitosamente.")

    def login(self) -> bool:
        """Performa el login con las credenciales."""
        # Get the current login page to extract fresh form state
        login_url = self.LOGIN_URL

        response = self.session.get(login_url)
        response.raise_for_status()

        # Extract all current form data
        form_data = self._extract_form_data(response.text, 'formLogin')

        if current_view_state := self._extract_view_state(response.text):
            self.view_state = current_view_state

        # Get the current session ID from cookies
        jsessionid = self.session.cookies.get('JSESSIONID')
        if jsessionid:
            login_url += f";jsessionid={jsessionid}"

        # Prepare login form data, preserving all existing form state
        login_form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'formLogin:loginButton',
            'javax.faces.partial.execute': '@all',
            'formLogin:loginButton': 'formLogin:loginButton',
            'formLogin': 'formLogin',
            'javax.faces.ViewState': self.view_state
        }

        # Add all existing form fields
        for key, value in form_data.items():
            if key not in login_form_data and not key.startswith('javax.faces'):
                login_form_data[key] = value

        # Override with our login credentials
        login_form_data.update({
            'formLogin:listBoxTipoUsuario_input': 'Prestador',
            'formLogin:listBoxTipoUsuario_focus': '',
            'formLogin:nit': "900073223",
            'formLogin:usuario': "9000732235",
            'formLogin:contraseña': "900073223",
        })

        # log.info(f"Attempting login")

        response = self.session.post(
            login_url,
            data=login_form_data,
            headers=self.ajax_headers(login_url)
        )
        response.raise_for_status()

        self.check_for_errors_in_ajax_response(response.text)

        # Check for successful login indicators
        if any(indicator in response.text.lower() for indicator in
               ['redirect', 'home.xhtml', 'success', 'bienvenido']):
            # log.info("Login successful")
            return True

        # If no clear error or success, try to access home page to verify
        home_response = self.session.get(self.HOME_URL)
        if home_response.status_code == 200 and 'login.xhtml' not in home_response.url:
            # log.info("Login successful - verified by accessing home page")
            return True
        else:
            raise Exception("Login failed - unable to access home page")

    def fill_documento_and_submit(self) -> Optional[str]:
        """Clica en buscar con el tipo de documento y documento establecido."""
        response = self.update_view_state(self.HOME_URL)
        self.ref_id_link = self.get_ref_id(response,
                                           'Solicitud de autorización de servicios y tecnologías en salud')
        ref_id = self.get_ref_id(response, 'Buscar')
        form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': ref_id,
            'javax.faces.partial.execute': '@all',
            'javax.faces.partial.render': 'main:a3tabladesolicuti',
            ref_id: ref_id,
            'main': 'main',
            self.ref_id_link: 'S,/pages/solicitudAut/consultasolicitudAut.xhtml',
            'main:numeroSolicitud': '0',
            'main:aniosolicitud': '0',
            'main:fechaInicialsolicitud_input': '',
            'main:fechafinalsolicitud_input': '',
            'main:estadoSolicitud_input': ' ',
            'main:estadoSolicitud_focus': '',
            'main:tipoAfiliadoSolicitud_input': self.tipo_documento,
            'main:tipoAfiliadoSolicitud_focus': '',
            'main:documentoAfiliadoSolicitud': self.documento,
            'main:ubicacionAfiliado_input': ' ',
            'main:ubicacionAfiliado_hinput': '',
            'main:diagnosticoPpal_input': ' ',
            'main:diagnosticoPpal_hinput': '',
            'main:udpSolicitud_input': ' ',
            'main:udpSolicitud_focus': '',
            'main:ServicioSolicitud_input': '',
            'main:ServicioSolicitud_focus': '',
            'main:a3tabladesolicuti:j_idt1398:filter': '',
            'main:a3tabladesolicuti:j_idt1407:filter': '',
            'javax.faces.ViewState': self.view_state
        }

        # log.info(f"Submetiendo formulario con {self.tipo_documento} {self.documento}")
        response = self.session.post(
            self.HOME_URL,
            data=form_data,
            headers=self.ajax_headers(self.HOME_URL)
        )
        response.raise_for_status()
        # log.info("Formulario submetido con éxito.")

        if 'No se encontraron registros' in response.text:
            raise SinAutorizacionesPorRadicar(
                f"Afiliado {self.tipo_documento}{self.documento} no tiene autorizaciones por raricar.")
        if 'No records found' in response.text:
            raise NroAutorizacionNoEncontrado("No se encontraron autorizaciones para este afiliado.")
        return response.text

    def click_in(self, name_btn, row_id) -> Optional[str]:
        """Clica en botón de lupa o en botón de 'Ver'."""
        form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': row_id,  # main:a3tabladesolicuti:0:j_idt484
            'javax.faces.partial.execute': '@all',
            'javax.faces.partial.render': 'main:tabViewDinamic',
            row_id: row_id,
            'main': 'main',
            self.ref_id_link: 'S,/pages/solicitudAut/consultasolicitudAut.xhtml',
            'main:numeroSolicitud': '0',
            'main:aniosolicitud': '0',
            'main:fechaInicialsolicitud_input': '',
            'main:fechafinalsolicitud_input': '',
            'main:estadoSolicitud_input': ' ',
            'main:estadoSolicitud_focus': '',
            'main:tipoAfiliadoSolicitud_input': self.tipo_documento,
            'main:tipoAfiliadoSolicitud_focus': '',
            'main:documentoAfiliadoSolicitud': self.documento,
            'main:ubicacionAfiliado_input': ' ',
            'main:ubicacionAfiliado_hinput': '',
            'main:diagnosticoPpal_input': ' ',
            'main:diagnosticoPpal_hinput': '',
            'main:udpSolicitud_input': ' ',
            'main:udpSolicitud_focus': '',
            'main:ServicioSolicitud_input': '',
            'main:ServicioSolicitud_focus': '',
            'main:a3tabladesolicuti:j_idt1398:filter': '',
            'main:a3tabladesolicuti:j_idt1407:filter': '',
            'javax.faces.ViewState': self.view_state
        }

        # log.info(f"Clicando en {name_btn}")
        response = self.session.post(
            self.HOME_URL,
            data=form_data,
            headers=self.ajax_headers(self.HOME_URL)
        )
        response.raise_for_status()
        if current_view_state := self._extract_view_state(response.text):
            self.view_state = current_view_state

        # log.info(f"{name_btn} ha sido clicad@")
        if name_btn == 'lupa' and "Información de la Atención" not in response.text:
            raise PasoNoProcesado(f'Modal al clicar {name_btn} no cargó')

        if name_btn == 'ver' and 'Fecha de Corte' not in response.text:
            raise PasoNoProcesado(f'Modal al clicar {name_btn} no cargó')
        return response.text

    def establish_date(self, response) -> Optional[str]:
        """Establece la fecha del día de hoy en el modal."""
        fecha_id = self.get_ref_id(response, 'Fecha')
        only_fecha_id = ':'.join(fecha_id.split(':')[:2])
        form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': fecha_id,  # main:j_idt1013:fechaPrestacion
            'javax.faces.partial.execute': fecha_id,  # main:j_idt1013:fechaPrestacion
            'javax.faces.behavior.event': 'dateSelect',
            'javax.faces.partial.event': 'dateSelect',
            only_fecha_id: only_fecha_id,  # main:j_idt1013
            f"{fecha_id}_input": f"{datetime.now():%d/%m/%Y} 12:00 AM",
            'javax.faces.ViewState': self.view_state
        }
        # log.info("Clicando en fecha del dia de hoy")
        response = self.session.post(
            self.HOME_URL,
            data=form_data,
            headers=self.ajax_headers(self.HOME_URL)
        )
        response.raise_for_status()
        # log.info("Fecha del dia de hoy clicada")
        return response.text

    def click_confirmar_fecha_prest(self, response):
        ref_id = self.get_ref_id(response, 'Botón Confirmar Fecha Prest')
        form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': ref_id,  # main:j_idt1013:fechaPrestacion
            'javax.faces.partial.execute': '@all',  # main:j_idt1013:fechaPrestacion
            'javax.faces.partial.render': 'main:a3tabladesolicuti main:pnlbotones main:pnldatossolicitud main:pnlMotivoEstado main:tableDetProductos main:panelAdjPresEfe',
            ref_id: ref_id,  # main:j_idt1013
            'main': 'main',
            self.ref_id_link: 'S,/pages/solicitudAut/consultasolicitudAut.xhtml',
            'main:numeroSolicitud': '0',
            'main:aniosolicitud': '0',
            'main:fechaInicialsolicitud_input': '',
            'main:fechafinalsolicitud_input': '',
            'main:estadoSolicitud_input': ' ',
            'main:estadoSolicitud_focus': '',
            'main:tipoAfiliadoSolicitud_input': self.tipo_documento,
            'main:tipoAfiliadoSolicitud_focus': '',
            'main:documentoAfiliadoSolicitud': self.documento,
            'main:ubicacionAfiliado_input': ' ',
            'main:ubicacionAfiliado_hinput': '',
            'main:diagnosticoPpal_input': ' ',
            'main:diagnosticoPpal_hinput': '',
            'main:udpSolicitud_input': ' ',
            'main:udpSolicitud_focus': '',
            'main:ServicioSolicitud_input': '',
            'main:ServicioSolicitud_focus': '',
            'main:a3tabladesolicuti:j_idt1398:filter': '',
            'main:a3tabladesolicuti:j_idt1407:filter': '',
            'javax.faces.ViewState': self.view_state
        }

        # log.info("Clicando en Confirmar fecha prest")
        response = self.session.post(
            self.HOME_URL,
            data=form_data,
            headers=self.ajax_headers(self.HOME_URL)
        )
        response.raise_for_status()
        # log.info("'Confirmar fecha prest' clicado")
        if 'El Nro. para Facturar es:' not in response.text:
            raise NroAutorizacionNoEncontrado(
                'Se esperaba Nro de Autorización en modal de lupa pero no fue encontrado.')
        return re.search(r'El Nro\. para Facturar es: AS(\d+)', response.text)[1]

    def close_modal(self):
        """Cierra el modal."""
        form_data = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'main:detallesolicitud',
            'javax.faces.partial.execute': 'main:detallesolicitud',
            'javax.faces.partial.render': 'main:cnsgPnlCentral',
            'javax.faces.behavior.event': 'close',
            'javax.faces.partial.event': 'close',
            'main': 'main',
            self.ref_id_link: 'S,/pages/solicitudAut/consultasolicitudAut.xhtml',
            'main:numeroSolicitud': '0',
            'main:aniosolicitud': '0',
            'main:fechaInicialsolicitud_input': '',
            'main:fechafinalsolicitud_input': '',
            'main:estadoSolicitud_input': ' ',
            'main:estadoSolicitud_focus': '',
            'main:tipoAfiliadoSolicitud_input': self.tipo_documento,
            'main:tipoAfiliadoSolicitud_focus': '',
            'main:documentoAfiliadoSolicitud': self.documento,
            'main:ubicacionAfiliado_input': ' ',
            'main:ubicacionAfiliado_hinput': '',
            'main:diagnosticoPpal_input': ' ',
            'main:diagnosticoPpal_hinput': '',
            'main:udpSolicitud_input': ' ',
            'main:udpSolicitud_focus': '',
            'main:ServicioSolicitud_input': '',
            'main:ServicioSolicitud_focus': '',
            'main:a3tabladesolicuti:j_idt1398:filter': '',
            'main:a3tabladesolicuti:j_idt1407:filter': '',
            'javax.faces.ViewState': self.view_state
        }
        # log.info("Clicando en close modal")
        response = self.session.post(
            self.HOME_URL,
            data=form_data,
            headers=self.ajax_headers(self.HOME_URL)
        )
        response.raise_for_status()
        # log.info("'close modal' clicado")

    @staticmethod
    def clean_medicamento_text(txt):
        """Realiza ajustes al valor del texto recibido."""
        txt = txt.replace(';', '')
        return txt

    def find_medicamentos(self, response):
        """Extrae los productos que estan en la tabla del modal."""
        soup = BeautifulSoup(response)
        table = soup.find('div', id='main:tableDetProductos')
        headers = [th.text.strip() for th in table.thead.find_all('th')]
        rows = []
        for tr in table.tbody.find_all('tr'):
            cells = tr.find_all('td')
            values = [self.clean_medicamento_text(td.get_text(strip=True)) for td in cells]
            for value in values:
                if 'No records found' in value:
                    raise NoRecordsInTable
            row_dict = dict(zip(headers, values))
            rows.append(row_dict)
        return rows

    def parse_aut_and_meds(self, nro_aut, meds) -> dict:
        """Crea un diccionario estándar para resumir la información."""
        return {
            'TIPO_DOCUMENTO': self.IDENTIFICACIONES.get(self.tipo_documento, '-'),
            'DOCUMENTO': self.documento,
            'NUMERO_AUTORIZACION': nro_aut,
            'DISPENSADO': None,
            'DETALLE_AUTORIZACION': [
                {
                    'NOMBRE_PRODUCTO': producto['Tecnologías'],
                    'CANTIDAD': producto['Cantidad'],
                }
                for producto in meds
            ],
        }

    def extract_nro_aut_and_meds(self, rows):
        """Navega por las filas que tienen autorizaciones aprobadas, realizando la siguiente lógica.

        1. Clica en lupa
        2. Se debe la autorizaicón buscar en el modal?
            2.1. No?. Entonces salta al paso 3
            2.2. Si?. Entonces:
            2.2.1. Establece la fecha
            2.2.2 Clica en 'Confirmar Fecha Prest'
            2.2.3 Extrae el número de autorización que cargó en pantalla.
        3. Con el modal abierto en el paso 2, se extraen los medicamentos.
        4. Se cierra el modal
        5. Fue extraido el número de autorización en el paso 2 ?
            5.1. Si?. Entonces el procesamiento de la fila ha sido terminado
            5.2. No?. Entonces:
            5.2.1. Clica en botón 'Ver'
            5.2.2. Extrae el número de autorización del modal que ha cargado.
        """

        nro_aut = ''
        auts, meds = [], []
        for i, row in enumerate(rows, 1):
            log.info(f'Fila {i}. Extrayendo información')
            resp = self.click_in('lupa', row.lupa_id)
            if row.buscar_aut:
                self.establish_date(resp)
                try:
                    nro_aut = self.click_confirmar_fecha_prest(resp)
                except NroAutorizacionNoEncontrado:
                    # todo enviar email avisando que nro de aut no tiene medicamentos.
                    continue
            try:
                # [{'Cantidad': '10', 'Renglón': '1', 'Tecnologías': '1495 BOLSA PARA COLOSTOMIA 57MM UNI'}]
                meds = self.find_medicamentos(resp)
            except NoRecordsInTable:
                # todo enviar email avisando que nro de aut no tiene medicamentos.
                continue
            self.close_modal()
            if not nro_aut:
                for _ in range(2):
                    if nro_aut:
                        break
                    resp = self.click_in('ver', row.ver_id)
                    soup = BeautifulSoup(resp)
                    ele = soup.find('span', id="main:tableDetProductosConcurrencia:0:numFacturarConcurrencia")
                    try:
                        nro_aut = ele.get_text(strip=True)
                    except AttributeError:
                        log.warning(
                            f"Fila {i}. Se esperaba Nro de Autorización en modal de 'Ver' pero no fue encontrado.")
            if not nro_aut:
                log.error(
                    'Se intentó dos veces encontrar el Nro de Aut en modal de ver pero no fue posible... reiniciando '
                    'scrapper'
                )
                raise RestartScrapper
            auts.append(self.parse_aut_and_meds(nro_aut, meds))
            nro_aut = ''
        return auts

    def close_session(self):
        """Close the session and clean up resources."""
        self.session.close()


class MutualScrapper(JSFPortalScraper):
    def __init__(self, tipo_documento, documento):
        super().__init__(tipo_documento, documento)

    @contextmanager
    def scrapping_in_progress(self):
        handler = log.handlers[0]  # Keep a reference
        original_formatter = handler.formatter
        add_user_id_to_formatter(handler, f"{self.tipo_documento}{self.documento}")
        yield
        ch.setFormatter(original_formatter)

    @retry(RestartScrapper, 2, 1)
    def find_user(self):  # sourcery skip: extract-method
        """Realiza login, busca usuario, analiza filas, tiene en cuenta las APPOBADO y retorna la información
            en un dict donde la llave es el nro de autorización y el value es la lista con los medicamentos.
        """
        with self.scrapping_in_progress():
            try:
                log.info('Accesando a site Mutual Ser y realizando login')
                self.open_site_and_login()
                log.info(f'Accesando formulario para submeter {self.tipo_documento}{self.documento}')
                html_response = self.go_to_form_and_submit()
                log.info('Extrayendo información de resultado')
                id_rows = parse_xml(html_response)
                result = self.extract_nro_aut_and_meds(id_rows)
                log.info('Proceso finalizado con éxito')
                return result
            except SinAutorizacionesPorRadicar as e:
                log.warning(str(e))
                return {'MSG': 'Usuario no posee autorizaciones en Mutual Ser.'}
            except NroAutorizacionNoEncontrado as e:
                log.warning(str(e))
                return {'MSG': 'Numero de autorización no encontrado para usuario.'}
            except NoRecordsInTable as e:
                log.warning(str(e))
                return {'MSG': 'Autorización sin medicamentos.'}
            except RestartScrapper:
                raise
            except Exception:
                traceback.print_exc()
                raise
            finally:
                self.close_session()

    def open_site_and_login(self):
        """Realiza los llamados POST equivalentes a abrir la página web e iniciar sesión."""
        self.initialize_session()  # Step 1: Inicia sesion
        self.select_user_type()  # Step 1.1: Selecciona tipo de usuario
        self.login()  # Step 2: Login

    def go_to_form_and_submit(self) -> str:
        """Se dirige al formulario y submete la información."""
        self.select_consulta_solicitudes()  # Step 3.1
        self.select_solicitud_aut()  # Step 3.2
        self.select_tipo_documento()  # Step 3.3
        return self.fill_documento_and_submit()  # Step 3.4


if __name__ == '__main__':
    scrapper = MutualScrapper('PT', '7136845')
    result = scrapper.find_user()
    pprint(result)
