from utils.config import IOU_THRESHOLD


def calcular_area_intersecao(box_a, box_b):
    x_a = max(box_a["x_min"], box_b["x_min"])
    y_a = max(box_a["y_min"], box_b["y_min"])
    x_b = min(box_a["x_max"], box_b["x_max"])
    y_b = min(box_a["y_max"], box_b["y_max"])

    intersecao = max(0, x_b - x_a) * max(0, y_b - y_a)
    area_a = (box_a["x_max"] - box_a["x_min"]) * (box_a["y_max"] - box_a["y_min"])
    area_b = (box_b["x_max"] - box_b["x_min"]) * (box_b["y_max"] - box_b["y_min"])
    uniao = float(area_a + area_b - intersecao)
    return (intersecao / uniao) if uniao > 0 else 0


def gerar_eventos(df_atual):
    """Gera apenas alertas de interacao da mao com produtos no frame atual."""
    eventos = []
    if df_atual.empty:
        return eventos

    for _, mao in df_atual[df_atual["classe"] == "mao"].iterrows():
        for _, produto in df_atual[df_atual["classe"] != "mao"].iterrows():
            if calcular_area_intersecao(mao.to_dict(), produto.to_dict()) >= IOU_THRESHOLD:
                eventos.append({"tipo": "interacao_mao", "produto": produto["classe"], "quantidade": 1})
                break

    return eventos
