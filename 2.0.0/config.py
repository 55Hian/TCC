"""Configuracao e caminhos pertencentes somente a versao 2.0.0."""
import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DATA = ROOT / "data"
MODELS = ROOT / "models"
CLASSES = os.getenv("TCC_CLASSES", "creme_leite,gelatina,cha,mao").split(",")
MODELOS = ("yolov8n", "yolo12n", "yolo26s", "yolo26m")
MODELO_PADRAO = os.getenv("TCC_MODELO_ATIVO", "yolo12n")
CAMERA_URL = os.getenv("TCC_CAMERA_URL", "http://192.168.15.59:81/stream")
DB_USER = os.getenv("POSTGRES_USER", "inventory")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "inventory-local")
DB_NAME = os.getenv("POSTGRES_DB", "inventory")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DATABASE_URL = os.getenv("TCC_DATABASE_URL") or "postgresql://{}:{}@{}:{}/{}".format(
    quote(DB_USER, safe=""), quote(DB_PASSWORD, safe=""), DB_HOST, DB_PORT, quote(DB_NAME, safe="")
)
API_BASE_URL = os.getenv("TCC_API_URL", "http://127.0.0.1:8000")
CAMERA_USB = os.getenv("TCC_CAMARA_SECUNDARIA", "0")
CAMERA_USB_BACKEND = os.getenv("TCC_CAMARA_BACKEND", "DSHOW")
VIDEO_BUFFER_SECONDS = int(os.getenv("TCC_VIDEO_SEGUNDOS_BUFFER", "1800"))
VIDEO_BEFORE_SECONDS = 20
VIDEO_AFTER_SECONDS = float(os.getenv("TCC_VIDEO_SEGUNDOS_DEPOIS", "10"))
CORRELATION_INTERVAL_SECONDS = int(os.getenv("TCC_CORRELACAO_INTERVALO_SEGUNDOS", "60"))
CORRELATION_WINDOW_SECONDS = int(os.getenv("TCC_CORRELACAO_JANELA_SEGUNDOS", "15"))
CORRELATION_WEIGHT_TOLERANCE = float(os.getenv("TCC_CORRELACAO_TOLERANCIA_PESO", "0.2"))
RAW_FRAMES = DATA / "frames"
ANNOTATIONS = DATA / "anotacoes"
YOLO_LABELS = DATA / "yolo"
DATASET = DATA / "dataset"
TRAINED_MODELS = MODELS / "trained"
HAND_MODEL = MODELS / "hand_landmarker.task"
VIDEO_DIR = DATA / "videos"


def camera_usb_source():
    try:
        return int(CAMERA_USB)
    except ValueError:
        return CAMERA_USB


def camera_usb_backend(cv2):
    backends = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF, "ANY": cv2.CAP_ANY}
    return backends.get(CAMERA_USB_BACKEND.upper())


def modelo_ativo():
    escolha = DATA / "modelo_ativo.txt"
    nome = escolha.read_text(encoding="utf-8").strip() if escolha.is_file() else MODELO_PADRAO
    return nome if nome in MODELOS else MODELO_PADRAO


def caminho_pesos():
    return TRAINED_MODELS / modelo_ativo() / "best.pt"
