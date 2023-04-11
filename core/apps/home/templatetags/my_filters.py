from django import template

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
