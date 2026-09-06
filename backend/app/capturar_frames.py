import argparse
import os
import time
import uuid
from pathlib import Path

import cv2

from services.camera_service import gerador_de_frames
from core.config import settings


def deve_capturar(ultimo_salvamento, agora, intervalo):
    """Decide se ja passou tempo suficiente para salvar um novo frame."""
    return (agora - ultimo_salvamento) >= intervalo


def gerar_nome_arquivo(contador):
    return time.strftime("frame_%Y%m%d_%H%M%S") + f"_{uuid.uuid4().hex[:8]}_{contador:04d}.jpg"


def capturar_frames(
    pasta_saida=None,
    intervalo=2.0,
    max_frames=0,
    mostrar_janela=True,
    fonte_frames=None,
):
    """Conecta na ESP32-CAM e salva frames automaticamente a cada `intervalo` segundos.

    `max_frames=0` significa captura ilimitada (encerra com Q ou Ctrl+C).
    `fonte_frames` permite injetar um generator alternativo (usado em testes).
    """
    pasta_saida = pasta_saida or settings.RAW_FRAMES_DIR
    os.makedirs(pasta_saida, exist_ok=True)
    ultimo_salvamento = 0.0
    contador = 0
    gerador = fonte_frames if fonte_frames is not None else gerador_de_frames(settings.ESP32_STREAM_URL)

    try:
        for frame in gerador:
            agora = time.time()

            if mostrar_janela:
                cv2.imshow("Captura automatica - Q encerra", frame)
                tecla = cv2.waitKey(1) & 0xFF
                if tecla in (ord("q"), ord("Q")):
                    print("[CAPTURA] Encerrado pelo usuario.")
                    break

            if deve_capturar(ultimo_salvamento, agora, intervalo):
                nome = gerar_nome_arquivo(contador)
                caminho = os.path.join(pasta_saida, nome)
                ok, jpeg = cv2.imencode(".jpg", frame)
                if not ok:
                    raise OSError("Falha ao codificar imagem JPEG")
                temporario = Path(caminho + ".part")
                try:
                    temporario.write_bytes(jpeg.tobytes())
                    os.replace(temporario, caminho)
                finally:
                    temporario.unlink(missing_ok=True)
                contador += 1
                ultimo_salvamento = agora
                print(f"[CAPTURA] Salvo: {caminho}")

            if max_frames > 0 and contador >= max_frames:
                print(f"[CAPTURA] Limite de {max_frames} frames atingido.")
                break
    except KeyboardInterrupt:
        print("[CAPTURA] Interrompido pelo usuario.")
    finally:
        if hasattr(gerador, "close"):
            gerador.close()
        if mostrar_janela:
            cv2.destroyAllWindows()

    return contador


def main():
    parser = argparse.ArgumentParser(
        description="Captura automatica de frames da ESP32-CAM para anotacao."
    )
    parser.add_argument("--saida", default=settings.RAW_FRAMES_DIR, help="Pasta para salvar os JPEGs.")
    parser.add_argument(
        "--intervalo",
        type=float,
        default=2.0,
        help="Intervalo entre capturas automaticas, em segundos.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Numero maximo de frames a capturar (0 = ilimitado).",
    )
    parser.add_argument(
        "--sem-janela",
        action="store_true",
        help="Executa sem abrir janela (modo headless, util para testes/servidores).",
    )
    args = parser.parse_args()
    capturar_frames(
        pasta_saida=args.saida,
        intervalo=max(0.1, args.intervalo),
        max_frames=max(0, args.max_frames),
        mostrar_janela=not args.sem_janela,
    )


if __name__ == "__main__":
    main()
