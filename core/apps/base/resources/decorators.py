import functools
from functools import wraps
from time import time

from core.settings import logger


def count_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.numcalls += 1
        print(f"* Call {wrapper.numcalls} of {func.__name__!r}")
        return func(*args, **kwargs)

    wrapper.numcalls = 0
    return wrapper


def logtime(tag):
    def decorator(func):
        @wraps(func)
        def wrapper(*fargs, **fkwargs):
            start = time()
            value = func(*fargs, **fkwargs)
            logger.info(f"{tag} {func.__name__!r} tardó {format(time() - start, '.4f')}s.")
            return value

        return wrapper

    return decorator
