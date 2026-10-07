"""
Teste manual do gravador com câmera real (webcam ou celular).

  python teste_manual_camera.py --listar --dshow      # descobre o índice da câmera
  python teste_manual_camera.py 1 --dshow             # captura, simula um evento e grava
  python teste_manual_camera.py http://IP:PORTA/video # celular via app de câmera IP
  python teste_manual_camera.py 1 --dshow --espera 5  # evento cedo: clipe com janela parcial

O clipe é salvo em videos_teste/evento_teste.mp4.
"""

import argparse
import logging
import threading
import time

import cv2

from backend.app.services.clip_service import GravadorRetirada


def listar(backend):
    for i in range(5):
        camera = cv2.VideoCapture(i) if backend is None else cv2.VideoCapture(i, backend)
        ok, frame = camera.read() if camera.isOpened() else (False, None)
        camera.release()
        detalhe = f"OK ({frame.shape[1]}x{frame.shape[0]})" if ok else "sem imagem"
        print(f"índice {i}: {detalhe}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fonte", nargs="?", default="0", help="índice da câmera ou URL")
    ap.add_argument("--listar", action="store_true", help="lista os índices que entregam imagem")
    ap.add_argument("--dshow", action="store_true", help="usa o backend DirectShow (Windows)")
    ap.add_argument("--espera", type=int, default=35, help="segundos de captura antes do evento simulado")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    backend = cv2.CAP_DSHOW if args.dshow else None

    if args.listar:
        listar(backend)
        return

    fonte = int(args.fonte) if args.fonte.isdigit() else args.fonte
    gravador = GravadorRetirada(fonte=fonte, pasta_saida="videos_teste", backend=backend)
    gravador.iniciar()

    print(f"Capturando por {args.espera} s antes do evento simulado...")
    time.sleep(args.espera)

    concluido = threading.Event()

    def ao_concluir(id_evento, caminho):
        print("Resultado:", caminho or "vídeo não gerado (veja o log)")
        concluido.set()

    gravador.gravar_retirada("teste", ao_concluir=ao_concluir)
    concluido.wait(timeout=30)
    gravador.parar()


if __name__ == "__main__":
    main()
