from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> core -> app -> backend -> raiz do repositorio
BASE_DIR = Path(__file__).resolve().parents[3]


MODELOS = ("yolov8n", "yolo12n", "yolo26s", "yolo26m")


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

    IOU_THRESHOLD: float = Field(default=0.10, gt=0, le=1)
    HAND_LANDMARKS_ENABLED: bool = True
    HAND_MODEL_PATH: str = str(BASE_DIR / "models" / "hand_landmarker.task")
    HAND_MAX_HANDS: int = Field(default=2, ge=1)
    HAND_CONTACT_MARGIN: float = Field(default=0.08, ge=0, le=0.5)
    INTERACTION_CONFIRM_SECONDS: float = Field(default=0.3, ge=0)
    INTERACTION_MOTION_MIN_RATIO: float = Field(default=0.1, gt=0, le=1)
    INTERACTION_MIN_SAMPLES: int = Field(default=3, ge=2)
    INTERACTION_MAX_GAP_SECONDS: float = Field(default=0.5, gt=0)
    INTERACTION_RELEASE_SECONDS: float = Field(default=0.6, gt=0)
    INTERACTION_RESET_SECONDS: float = Field(default=2.0, gt=0)
    INTERVALO_PROCESSAMENTO: float = 0.05

    RAW_FRAMES_DIR: str = str(BASE_DIR / "data" / "raw_frames")
    LABELME_ANNOTATIONS_DIR: str = str(BASE_DIR / "data" / "labelme_annotations")
    YOLO_LABELS_DIR: str = str(BASE_DIR / "data" / "yolo_labels")
    DATASET_DIR: str = str(BASE_DIR / "data" / "dataset")

    # Unica selecao para treinamento e inferencia. Reinicie o processo ao alterar.
    MODELO_ATIVO: Literal["yolov8n", "yolo12n", "yolo26s", "yolo26m"] = "yolo12n"
    PRETRAINED_MODELS_DIR: str = str(BASE_DIR / "models" / "pretrained")
    TRAINED_MODELS_DIR: str = str(BASE_DIR / "models" / "trained")
    TRAINING_PROJECT: str = str(BASE_DIR / "experiments" / "runs")
    BENCHMARKS_DIR: str = str(BASE_DIR / "experiments" / "benchmarks")

    @property
    def BASE_MODEL(self):
        return str(Path(self.PRETRAINED_MODELS_DIR) / f"{self.MODELO_ATIVO}.pt")

    @property
    def MODEL_PATH(self):
        return str(Path(self.TRAINED_MODELS_DIR) / self.MODELO_ATIVO / "best.pt")

    @property
    def TRAINING_NAME(self):
        return self.MODELO_ATIVO

    USE_EXTERNAL_VALIDATION_DATASET: bool = False
    EXTERNAL_VALIDATION_DATASET_DIR: str = str(BASE_DIR / "data" / "external_validation")
    EXTERNAL_VALIDATION_DATASET_YAML: str = str(BASE_DIR / "data" / "external_validation" / "data.yaml")


settings = Settings()
