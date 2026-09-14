"""Saída local de eventos da CLI; mantém a publicação HTTP desativada."""
import datetime


def enviar_eventos(lista_eventos):
    """Acrescenta o horário local e informa o evento no console."""
    if not lista_eventos:
        return
    for evento in lista_eventos:
        evento["timestamp"] = datetime.datetime.now().isoformat()
        try:
            print(f"[API] Evento enviado: {evento['tipo']} -> {evento['produto']}")
        except Exception:
            print(f"[API_ERRO] Falha de conexao com backend para o evento {evento['tipo']}.")
