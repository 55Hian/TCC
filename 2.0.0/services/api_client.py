"""Envia eventos de interacao do monitoramento para a rota de eventos da API."""
import json
import urllib.request

from config import API_BASE_URL


def enviar_evento_camera(evento):
    dados = {chave: valor for chave, valor in evento.items() if chave != "timestamp"}
    corpo = json.dumps(dados).encode("utf-8")
    requisicao = urllib.request.Request(
        API_BASE_URL.rstrip("/") + "/api/eventos",
        data=corpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(requisicao, timeout=4) as resposta:
        return json.loads(resposta.read().decode("utf-8"))
