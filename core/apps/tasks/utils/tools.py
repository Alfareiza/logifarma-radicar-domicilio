from datetime import datetime

from pytz import timezone


def moment():
    return datetime.now(tz=timezone('America/Bogota'))
