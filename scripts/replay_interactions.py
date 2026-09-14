"""Reproduz video local e exporta eventos para calibracao, sem publicar na API."""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "app"))
from services.event_service import ServicoEventos
from services.interaction_overlay import desenhar_interacoes
from services.vision_service import ServicoVisao
from core.config import settings


def avaliar_eventos(eventos, esperados):
    correspondencias = set()
    acertos = 0
    for evento in eventos:
        for indice, item in enumerate(esperados):
            if (indice not in correspondencias and item["produto"] == evento["produto"]
                    and item["inicio"] <= evento["segundo"] <= item["fim"] + settings.INTERACTION_CONFIRM_SECONDS):
                correspondencias.add(indice)
                acertos += 1
                break
    return dict(corretos=acertos, falsos_ou_duplicados=len(eventos)-acertos,
                perdidos=len(esperados)-acertos)


def gerar_eventos_baseline(detections):
    """Reproduz a regra histórica: primeiro produto sobreposto por mão e imagem."""
    from services.event_service import calcular_area_intersecao
    registros = detections.to_dict("records")
    atuais = []
    for mao in registros:
        if mao["classe"] != "mao":
            continue
        for produto in registros:
            if produto["classe"] != "mao" and calcular_area_intersecao(mao, produto) >= settings.IOU_THRESHOLD:
                atuais.append(dict(tipo="interacao_mao", produto=produto["classe"], quantidade=1))
                break
    return atuais


def _validar_saidas(opcoes, argumentos):
    # Saidas devem ser novas para evitar sobrescrever videos/anotacoes.
    for saida in (opcoes.output, opcoes.annotated_video):
        if saida is not None and saida.exists():
            argumentos.error(f"Saida ja existe: {saida}")


def _montar_resultado(opcoes, quadros, fps, tempo_decorrido, eventos):
    """Agrupa métricas e avaliação sem misturar leitura de vídeo e serialização."""
    relatorio = dict(video=str(opcoes.video), frames=quadros, fps_video=fps,
                  fps_processamento=quadros / tempo_decorrido if tempo_decorrido else 0,
                  modo="baseline" if opcoes.baseline else ("iou_temporal" if opcoes.iou_only else "landmarks_temporal"),
                  parametros={chave: valor for chave, valor in settings.model_dump().items()
                              if chave.startswith(("INTERACTION_", "HAND_CONTACT_", "IOU_"))},
                  eventos=eventos)
    if opcoes.annotations:
        relatorio["avaliacao"] = avaliar_eventos(eventos, json.loads(opcoes.annotations.read_text(encoding="utf-8")))
    return relatorio


def _validar_video(captura, caminho_video):
    """Exige uma fonte aberta e taxa de quadros válida para calcular os instantes."""
    if not captura.isOpened():
        raise ValueError(f"Nao foi possivel abrir {caminho_video}")
    fps = captura.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        raise ValueError("Video sem FPS valido.")
    return fps


def main():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("video", type=Path)
    argumentos.add_argument("--output", type=Path, required=True)
    argumentos.add_argument("--weights")
    argumentos.add_argument("--device", help="cpu ou indice da GPU; padrao do YOLO quando omitido.")
    argumentos.add_argument("--iou-only", action="store_true", help="Desativa landmarks; mantem regra temporal.")
    argumentos.add_argument("--baseline", action="store_true", help="Regra original: primeiro produto por mao/frame.")
    argumentos.add_argument("--annotated-video", type=Path)
    argumentos.add_argument("--annotations", type=Path, help="JSON: lista de produto/inicio/fim em segundos.")
    opcoes = argumentos.parse_args()
    _validar_saidas(opcoes, argumentos)
    settings.HAND_LANDMARKS_ENABLED = not (opcoes.iou_only or opcoes.baseline)
    captura = cv2.VideoCapture(str(opcoes.video))
    visao, gravador = None, None
    try:
        fps = _validar_video(captura, opcoes.video)
        visao = ServicoVisao(opcoes.weights, device=opcoes.device)
        servico = ServicoEventos()
        eventos, quadros = [], 0
        inicio = time.perf_counter()
        while True:
            ok, imagem = captura.read()
            if not ok:
                break
            segundo = quadros / fps
            deteccoes = visao.processar_frame(imagem, timestamp=segundo)
            if opcoes.baseline:
                atuais = gerar_eventos_baseline(deteccoes)
            else:
                atuais = servico.processar(deteccoes, segundo)
            eventos.extend(dict(evento, segundo=segundo) for evento in atuais)
            if opcoes.annotated_video:
                if gravador is None:
                    gravador = cv2.VideoWriter(str(opcoes.annotated_video), cv2.VideoWriter_fourcc(*"mp4v"),
                                             fps, (imagem.shape[1], imagem.shape[0]))
                    if not gravador.isOpened():
                        raise RuntimeError("Falha ao criar video anotado.")
                gravador.write(desenhar_interacoes(imagem, servico))
            quadros += 1
        tempo_decorrido = time.perf_counter() - inicio
        relatorio = _montar_resultado(opcoes, quadros, fps, tempo_decorrido, eventos)
        opcoes.output.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{quadros} frames; {len(eventos)} eventos; {relatorio['fps_processamento']:.1f} FPS. {opcoes.output}")
    finally:
        captura.release()
        if gravador is not None:
            gravador.release()
        if visao is not None:
            visao.fechar()




# Compatibilidade de importação com os nomes anteriores.
def evaluate(events, expected):
    """Aceita os parâmetros nomeados da interface anterior."""
    return avaliar_eventos(events, expected)

if __name__ == "__main__":
    main()
