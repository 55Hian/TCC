"""Visualizacao local das deteccoes e associacoes usadas na decisao."""
import cv2

from services.hand_service import HAND_CONNECTIONS


def desenhar_interacoes(imagem, eventos):
    saida = imagem.copy()
    confirmados = {item["produto_id"] for item in eventos.diagnostics if item["estado"] == "confirmada"}
    for item in eventos.detections:
        cor = (0, 200, 0) if item["track_id"] in confirmados else (0, 200, 255)
        a = (int(item["x_min"]), int(item["y_min"]))
        b = (int(item["x_max"]), int(item["y_max"]))
        cv2.rectangle(saida, a, b, cor, 2)
        cv2.putText(saida, f'{item["classe"]} #{item["track_id"]}', a,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 1)
        _desenhar_pontos(saida, item, cor)
    for indice, item in enumerate(eventos.diagnostics):
        cv2.putText(saida, f'Mao {item["mao_id"]} -> produto {item["produto_id"]}: {item["estado"]} {item["interpretacao"]}',
                    (10, 20 + indice * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    return saida


def _desenhar_pontos(saida, item, cor):
    """Desenha os segmentos e os índices usados no diagnóstico do contato."""
    pontos = item.get("landmarks")
    if isinstance(pontos, (list, tuple)) and len(pontos) == 21:
        for inicio, fim in HAND_CONNECTIONS:
            cv2.line(saida, tuple(map(int, pontos[inicio])), tuple(map(int, pontos[fim])), cor, 1)
        for indice, ponto in enumerate(pontos):
            posicao = tuple(map(int, ponto))
            cv2.circle(saida, posicao, 3, (255, 0, 255), -1)
            cv2.putText(saida, str(indice), posicao, cv2.FONT_HERSHEY_SIMPLEX, 0.3, cor, 1)


# Compatibilidade de importação com os nomes anteriores.
def draw_interactions(frame, events):
    """Aceita os parâmetros nomeados da interface anterior."""
    return desenhar_interacoes(frame, events)
