import contextlib
from datetime import datetime

from RPA.Desktop.OperatingSystem import psutil
from psutil import process_iter
from pytz import timezone


def moment():
    return datetime.now(tz=timezone('America/Bogota'))


def kill_zombies():
    for p in process_iter(["name"]):
        name = p.info["name"] or ""
        if "chrome" in name.lower() or "chromedriver" in name.lower():
            with contextlib.suppress(Exception):
                p.kill()
