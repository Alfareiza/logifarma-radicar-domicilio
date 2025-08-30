import re
from datetime import datetime
from typing import Any

from django import template
from django.core.exceptions import ValidationError
from django.forms import Form

register = template.Library()


@register.filter
def get_item(dct, key):
    return dct.get(key)


@register.filter
def calc_percent(base, goal):
    """
    >>> calc_percent(1394, 4000)
    35
    >>> calc_percent(1408, 4000)
    35
    """
    return int(round((base / goal) * 100, 0))


@register.filter
def calc_devices(rads):
    return {rad['ip'] for rad in rads}


@register.filter
def jsonify(dct):
    import json
    return json.dumps(dct)


@register.filter
def remove_code(txt):
    """Remove the code of the product.
    >>> remove_code("M00835 DAPAGLIFLOZINA 10.MG/1.U TABLETA RECUBIERTA")
    'DAPAGLIFLOZINA 10.MG/1.U TABLETA RECUBIERTA'
    """
    return re.sub(r'^M\d+\s+', '', txt)


@register.filter
def row_color(rad) -> str:
    """Determina el color de la fila con base en la cantidad de días desde que se creó hasta hoy."""
    hoy = datetime.now().date()
    diferencia = hoy - rad.datetime.date()
    if diferencia.days >= 5:
        return "#ffd5d5"  # Red
    elif diferencia.days >= 3:
        return "#fffddf"  # Yellow
    elif diferencia.days >= 1:
        return "#e6ffda"  # Green
    else:
        return "#d4fcc0"  # Green

@register.filter
def get_modal_context(element: Form) -> dict[str, Any] | None:
    """Extract the error code from error form response.
    Example of return:
    {'modal_type': 'blocked_number', 'modal_title': 'Teléfono no permitido',
 'modal_body': 'Lo sentimos, no está permitido este número celular:<br><br>3205458076<br><br>Para más información comunícate con nosotros al 333 033 3124',
 'button_text': 'Entendido',
 'button_color_class': 'bg-blue-600',
 'button_color_hover': 'bg-blue-400'}
    """
    try:
        return list(element.errors.as_data().values())[0][0].params
    except AttributeError as e:
        print(e)


