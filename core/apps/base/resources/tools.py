from core.settings import BASE_DIR, logger


def convert_bytes(size):
    """ Convert bytes to KB, or MB or GB"""
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return "%3.1f %s" % (size, x)
        size /= 1024.0


def read_json(pathfile):
    """Read a json and return a dict"""
    import json
    fp = BASE_DIR / f'core/apps/base/{pathfile}'
    with open(fp) as file:
        data = json.load(file)

    return data


def del_file(filepath):
    """
    Elimina el archivo indicado.
    :param filepath: 'tmp_logifrm/formula_medica.png'
    :return: None
    """
    try:
        import os
        os.remove(filepath)
        logger.info(f"Imagen ==> {filepath} <== eliminada")
    except FileNotFoundError as e:
        logger.error('Error al borrar el archivo: ', e)
