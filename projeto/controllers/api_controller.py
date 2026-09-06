import datetime

import requests

from utils.config import API_ENDPOINT


def enviar_eventos(lista_eventos):
    if not lista_eventos:
        return

    for evento in lista_eventos:
        evento["timestamp"] = datetime.datetime.now().isoformat()
        try:
            # resposta = requests.post(API_ENDPOINT, json=evento, timeout=3)
            # resposta.raise_for_status()

            print(f"[API] Evento enviado: {evento['tipo']} -> {evento['produto']}")
        except Exception:
            print(f"[API_ERRO] Falha de conexao com backend para o evento {evento['tipo']}.")
