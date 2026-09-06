"""Proxy do stream MJPEG da ESP32-CAM para o navegador."""
import cv2
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from core.config import settings
from services.camera_service import gerador_de_frames

router = APIRouter(prefix="/api", tags=["stream"])


def _frames_mjpeg():
    # reencoda em JPEG pois camera_service ja decodifica para numpy (reuso sem duplicar logica de rede)
    for frame in gerador_de_frames(settings.ESP32_STREAM_URL):
        ok, jpg = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
        )


@router.get("/stream")
def stream_camera():
    """Se a ESP32-CAM estiver inacessivel, a resposta fica aberta sem enviar frames
    (camera_service tenta reconectar indefinidamente); o front deve tratar timeout."""
    return StreamingResponse(
        _frames_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
