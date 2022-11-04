import json

import requests


def call_api_eps(serial):
    url = "https://genesis.cajacopieps.com/api/api_qr.php"
    payload = {"function": "p_mostrar_autorizacion",
               "serial": str(serial),
               "nit": "900073223"}
    headers = {'Content-Type': 'text/plain'}
    data = json.dumps(payload, indent=2)
    response = requests.request("POST", url, headers=headers, data=data)
    return json.loads(response.text.encode('utf8'))


def api2():
    ...
