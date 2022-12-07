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


def parse_agent(agent: str) -> str:
    """
    Recibe el agente que hace el request y devuelve algunos valores
    :param agent: Representación del agent
    :return: Agente resumido
    >>> parse_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36')
    '(Windows NT 10.0; Win64; x64) Chrome/108.0.0.0'
    >>> parse_agent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/17.0 Chrome/96.0.4664.104 Safari/537.36')
    '(X11; Linux x86_64) SamsungBrowser/17.0'
    >>> parse_agent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36')
    '(X11; Linux x86_64) Chrome/107.0.0.0'
    >>> parse_agent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15(KHTML, like Gecko) Version/15.2 Safari/605.1.15')
    '(Macintosh; Intel Mac OS X 10_15_6) Version/15.2'
    >>> parse_agent('Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36')
    '(Linux; Android 13; Pixel 6) Chrome/108.0.0.0'
    """
    try:
        start_os = agent.find('(')
        end_os = agent.find(')')
        os_device = agent[start_os:end_os + 1]
        start_brw = len(agent) - agent[::-1].find(')') + 1
        brw_device = agent[start_brw:].split(' ')[0]
    except Exception as e:
        logger.warning("Parsear el agent=", agent, "ERROR=", e)
        return agent
    return f'{os_device}({brw_device})'
