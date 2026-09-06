import argparse
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


def treinar(modelo_base, nome_experimento, batch=4, workers=2):
    from ultralytics import YOLO

    t0 = time.time()
    modelo = YOLO(modelo_base)
    modelo.train(
        data=str(BASE_DIR / "data" / "dataset" / "data.yaml"),
        epochs=50,
        imgsz=640,
        project=str(BASE_DIR / "experiments" / "treinamentos"),
        name=nome_experimento,
        device=0,
        batch=batch,
        workers=workers,
    )
    print(f"tempo_total_treino_{nome_experimento}=" + str(time.time() - t0))


def main():
    parser = argparse.ArgumentParser(description="Treina um experimento YOLO na GPU. Execute apenas um treino por vez.")
    parser.add_argument("modelo_base", help="Nome em models/pretrained ou caminho para pesos .pt")
    parser.add_argument("nome_experimento")
    parser.add_argument("batch", nargs="?", type=int, default=4)
    parser.add_argument("workers", nargs="?", type=int, default=2)
    parser.add_argument("--check", action="store_true", help="Valida modelo e dataset sem iniciar treino")
    args = parser.parse_args()
    modelo = Path(args.modelo_base)
    if modelo.name == args.modelo_base:
        modelo = BASE_DIR / "models" / "pretrained" / modelo
    if not modelo.is_file():
        parser.error(f"Modelo nao encontrado: {modelo}")
    if args.batch <= 0 or args.workers < 0:
        parser.error("batch deve ser positivo e workers nao negativo")
    import yaml
    dataset = BASE_DIR / "data" / "dataset" / "data.yaml"
    if not dataset.is_file():
        parser.error(f"Dataset nao encontrado: {dataset}")
    config = yaml.safe_load(dataset.read_text(encoding="utf-8"))
    pasta = Path(config.get("path", dataset.parent))
    if not pasta.is_absolute():
        parser.error("O path do dataset deve ser absoluto; gere novamente pelo pipeline de treino.")
    for split in ("train", "val"):
        imagens = pasta / config[split]
        if not imagens.is_dir() or not any(imagens.iterdir()):
            parser.error(f"Split ausente ou vazio: {imagens}")
    if args.check:
        print(f"OK: modelo={modelo}; dataset={dataset}; treino nao iniciado")
        return
    treinar(str(modelo), args.nome_experimento, args.batch, args.workers)


if __name__ == "__main__":
    main()
