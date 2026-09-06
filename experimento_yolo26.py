import sys
import time

from ultralytics import YOLO


def treinar(modelo_base, nome_experimento, batch=4, workers=2):
    t0 = time.time()
    modelo = YOLO(modelo_base)
    modelo.train(
        data=r"G:\000. TCC\dataset\data.yaml",
        epochs=50,
        imgsz=640,
        project=r"G:\000. TCC\treinamentos",
        name=nome_experimento,
        device=0,
        batch=batch,
        workers=workers,
    )
    print(f"tempo_total_treino_{nome_experimento}=" + str(time.time() - t0))


if __name__ == "__main__":
    modelo_base = sys.argv[1]
    nome_experimento = sys.argv[2]
    # GTX 1650 tem 4GB de VRAM: batch alto (padrão 16) estoura a memória
    # dedicada e o driver passa a usar memória compartilhada, deixando o
    # treino ~100x mais lento. batch=4 (modelos S) / batch=2 (modelos M) cabem na VRAM.
    batch = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    treinar(modelo_base, nome_experimento, batch, workers)
