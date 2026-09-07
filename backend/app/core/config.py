from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> core -> app -> backend -> raiz do repositorio
BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        env_prefix="TCC_",
        extra="ignore",
    )

    ESP32_STREAM_URL: str = "http://192.168.15.59:81/stream"
    API_ENDPOINT: str = "http://localhost:8000/api/eventos"

    CLASSES: list[str] = ["creme_leite", "gelatina", "cha", "mao"]
    EXTERNAL_CLASSES: list[str] = [
        "DUCOCO",
        "coca_cola",
        "creme_nestle",
        "extrato_turma_monica",
        "garrafa_agua",
        "margarina_dorianna",
        "pasta_colgate",
        "sabonete_dove",
        "sardinha_coqueiro",
        "todinho",
    ]

    IOU_THRESHOLD: float = 0.10
    INTERVALO_PROCESSAMENTO: float = 0.05

    RAW_FRAMES_DIR: str = str(BASE_DIR / "data" / "raw_frames")
    LABELME_ANNOTATIONS_DIR: str = str(BASE_DIR / "data" / "labelme_annotations")
    YOLO_LABELS_DIR: str = str(BASE_DIR / "data" / "yolo_labels")
    DATASET_DIR: str = str(BASE_DIR / "data" / "dataset")

    TRAINING_PROJECT: str = str(BASE_DIR / "experiments" / "treinamentos")
    TRAINING_NAME: str = "modelo_produtos"
    MODEL_PATH: str = str(BASE_DIR / "experiments" / "treinamentos" / "modelo_produtos" / "weights" / "best.pt")

    # Arquitetura base usada para treinar. Troque aqui para alternar entre os 4 modelos em models/pretrained/.
    PRETRAINED_MODELS_DIR: str = str(BASE_DIR / "models" / "pretrained")
    BASE_MODEL: str = str(BASE_DIR / "models" / "pretrained" / "yolo12n.pt")

    USE_EXTERNAL_VALIDATION_DATASET: bool = False
    EXTERNAL_VALIDATION_DATASET_DIR: str = str(BASE_DIR / "data" / "external_validation")
    EXTERNAL_VALIDATION_DATASET_YAML: str = str(BASE_DIR / "data" / "external_validation" / "data.yaml")


settings = Settings()
