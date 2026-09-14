"""Proxy MJPEG alimentado pela conexao compartilhada do backend."""
import asyncio
import anyio

import cv2
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from services.shared_camera import camera

router = APIRouter(prefix="/api", tags=["stream"])


async def _frames_mjpeg(request):
    identificador_consumidor = await anyio.to_thread.run_sync(camera.adquirir, "mjpeg")
    try:
        sequencia = 0
        while not await request.is_disconnected():
            item = await asyncio.to_thread(camera.aguardar_frame, sequencia)
            if item is None:
                if camera.status()["status"] == "parado":
                    break
                continue
            sequencia, imagem = item
            ok, jpg = await asyncio.to_thread(cv2.imencode, ".jpg", imagem)
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
    finally:
        with anyio.CancelScope(shield=True):
            await anyio.to_thread.run_sync(camera.liberar, identificador_consumidor)


@router.get("/stream")
def stream_camera(request: Request):
    return StreamingResponse(_frames_mjpeg(request),
        media_type="multipart/x-mixed-replace; boundary=frame")
