from datetime import datetime
from typing import List


def order_radicados_by_day(radicados: List[dict]) -> dict:
    """
    A partir de una lista con n cantidad de radicados,
    crea un diccionário donde la llave es el número del día y su
    value es la lista con los radicados de aquel dia.
    """
    res = {}
    for rad in radicados:
        day = str(rad['datetime'].day)
        if day not in res:
            res[day] = []
        del rad['datetime']
        res[day].append(rad)

    today = datetime.now().day
    if today not in res:
        res[today] = []
    return res
