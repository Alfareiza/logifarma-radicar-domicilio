import functools
from datetime import timedelta, datetime
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
            title = ''
            # If the tag is API and the url is coming
            if tag == 'API' and fargs:
                if 'medicarws' in fargs[0]:
                    title = f"{tag} MEDICAR"
                if 'cajacopieps' in fargs[0]:
                    title = f"{tag} CAJACOPI"
                if 'autorizacion' in fargs[2]:
                    title = f"{title} {fargs[2]['autorizacion']}"
                if 'serial' in fargs[2]:
                    title = f"{title} {fargs[2]['serial']}"
                if 'Centro' in fargs[2]:
                    title = f"Centro {fargs[2]['Centro']}"
            if tag == 'INV' and fargs:
                title = f"{title} {fargs[1]}"
            logger.info(f"{title or tag} {func.__name__!r} tardó {format(time() - start, '.4f')}s.")
            return value

        return wrapper

    return decorator


def ignore_unhashable(func):
    uncached = func.__wrapped__
    attributes = functools.WRAPPER_ASSIGNMENTS + ('cache_info', 'cache_clear')

    @functools.wraps(func, assigned=attributes)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TypeError as error:
            if 'unhashable type' in str(error):
                return uncached(*args, **kwargs)
            raise

    wrapper.__uncached__ = uncached
    return wrapper


def hash_dict(func):
    """Transform mutable dictionary into immutable
    Useful to be compatible with cache
    """

    class HDict(dict):
        def __hash__(self):
            return hash(frozenset(self.items()))

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        args = tuple([HDict(arg) if isinstance(arg, dict) else arg for arg in args])
        kwargs = {k: HDict(v) if isinstance(v, dict) else v for k, v in kwargs.items()}
        return func(*args, **kwargs)

    return wrapped


def timed_lru_cache(seconds: int, maxsize: int = 4):
    def wrapper_cache(func):
        func = functools.lru_cache(maxsize=maxsize)(func)
        func.lifetime = timedelta(seconds=seconds)
        func.expiration = datetime.utcnow() + func.lifetime

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if datetime.utcnow() >= func.expiration:
                func.cache_clear()
                func.expiration = datetime.utcnow() + func.lifetime

            return func(*args, **kwargs)

        return wrapped_func

    return wrapper_cache
