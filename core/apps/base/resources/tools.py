import shutil

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
    from pathlib import Path
    fp = BASE_DIR / f'core/apps/base/{pathfile}'
    with open(fp) as file:
        data = json.load(file)

    return data


def del_folder(MEDIA_ROOT):
    """
    Elimina la carpeta donde se guardó la imagen y
    lo que en ella se encuentre.
    :param MEDIA_ROOT: 'tmp_logifrm/formula_medica.png'
    :return: None
    """
    try:
        shutil.rmtree(MEDIA_ROOT)
    except FileNotFoundError as e:
        logger.error('Error al borrar la carpeta: ', e)