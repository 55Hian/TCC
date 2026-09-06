ESP32_STREAM_URL = "http://192.168.15.59:81/stream"
API_ENDPOINT = "http://localhost:8000/api/eventos"

CLASSES = ["creme_leite", "gelatina", "cha", "mao"]
EXTERNAL_CLASSES = [
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

IOU_THRESHOLD = 0.15
INTERVALO_PROCESSAMENTO = 0.05

DATASET_DIR = "dataset"
TRAINING_PROJECT = "treinamentos"
TRAINING_NAME = "modelo_produtos"
MODEL_PATH = "treinamentos/modelo_produtos/weights/best.pt"

# Arquitetura base usada para treinar (ex.: "yolov8n.pt", "yolo12n.pt"). Troque aqui para alternar.
BASE_MODEL = "yolo26m.pt"

USE_EXTERNAL_VALIDATION_DATASET = False
EXTERNAL_VALIDATION_DATASET_DIR = r"G:\000. TCC\yolo"
EXTERNAL_VALIDATION_DATASET_YAML = r"G:\000. TCC\yolo\data.yaml"
