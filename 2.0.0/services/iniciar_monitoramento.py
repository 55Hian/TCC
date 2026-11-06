import json
import threading
import time
import urllib.request
from collections import deque
from math import hypot
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parents[1]


class Configuracoes:
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

    IOU_THRESHOLD = 0.10
    HAND_LANDMARKS_ENABLED = True
    HAND_MODEL_PATH = str(BASE_DIR / "models" / "hand_landmarker.task")
    HAND_MAX_HANDS = 2
    HAND_CONTACT_MARGIN = 0.08
    INTERACTION_CONFIRM_SECONDS = 0.3
    INTERACTION_MOTION_MIN_RATIO = 0.1
    INTERACTION_MIN_SAMPLES = 3
    INTERACTION_MAX_GAP_SECONDS = 0.5
    INTERACTION_RELEASE_SECONDS = 0.6
    INTERACTION_RESET_SECONDS = 2.0
    INTERVALO_PROCESSAMENTO = 0.05

    MODELO_ATIVO = "yolo12n"
    TRAINED_MODELS_DIR = str(BASE_DIR / "models" / "trained")
    USE_EXTERNAL_VALIDATION_DATASET = False

    @property
    def MODEL_PATH(self):
        return str(Path(self.TRAINED_MODELS_DIR) / self.MODELO_ATIVO / "best.pt")


settings = Configuracoes()
LIMITE_BUFFER_BYTES = 4 * 1024 * 1024
JANELA_MOVIMENTO_SEGUNDOS = 0.6
TOLERANCIA_TEMPO_SEGUNDOS = 1e-9

# Inclui segmentos dos dedos e contorno da palma.
HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
)


def gerador_de_frames(url_stream, stop_event=None, on_status=None):
    sinal_parada = stop_event if stop_event is not None else threading.Event()
    informar_status = on_status or (lambda status, erro=None: None)
    while not sinal_parada.is_set():
        try:
            informar_status("conectando")
            print(f"[CAMERA] Conectando em {url_stream}...")
            with urllib.request.urlopen(url_stream, timeout=3) as fluxo:
                yield from _decodificar_resposta(fluxo, sinal_parada)
        except Exception as erro:
            informar_status("reconectando", str(erro))
            print(f"[CAMERA] Falha: {erro}. Reconectando em 2 segundos...")
            sinal_parada.wait(2)


def _decodificar_resposta(fluxo, sinal_parada):
    dados_pendentes = b""
    while not sinal_parada.is_set():
        bloco = fluxo.read1(4096)
        if not bloco:
            raise ConnectionError("stream encerrado")
        dados_pendentes += bloco
        if len(dados_pendentes) > LIMITE_BUFFER_BYTES:
            raise ValueError("JPEG excedeu limite de buffer")
        while True:
            inicio = dados_pendentes.find(b"\xff\xd8")
            if inicio < 0:
                dados_pendentes = dados_pendentes[-1:]
                break
            dados_pendentes = dados_pendentes[inicio:]
            fim = dados_pendentes.find(b"\xff\xd9", 2)
            if fim < 0:
                break
            jpg, dados_pendentes = dados_pendentes[: fim + 2], dados_pendentes[fim + 2 :]
            imagem = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if imagem is not None:
                yield imagem


class ServicoMaos:
    def __init__(self):
        if not Path(settings.HAND_MODEL_PATH).is_file():
            raise RuntimeError("Modelo da mao ausente. Execute scripts/setup_hands.py.")
        try:
            import mediapipe as mp
        except ImportError as erro:
            raise RuntimeError("Instale requirements-hands.txt para usar os pontos da mao.") from erro
        self.mp = mp
        self.last_timestamp = -1
        opcoes_detector = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=settings.HAND_MODEL_PATH),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=settings.HAND_MAX_HANDS,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(opcoes_detector)

    def processar_frame(self, frame, timestamp):
        instante_milissegundos = max(self.last_timestamp + 1, int(timestamp * 1000))
        self.last_timestamp = instante_milissegundos
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultado = self.detector.detect_for_video(
            self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), instante_milissegundos
        )
        altura, largura = frame.shape[:2]
        deteccoes = []
        for landmarks in resultado.hand_landmarks:
            deteccoes.append(_converter_pontos(landmarks, largura, altura))
        return deteccoes

    def fechar(self):
        self.detector.close()

    close = fechar


def _converter_pontos(landmarks, largura, altura):
    pontos = [(ponto.x * largura, ponto.y * altura) for ponto in landmarks]
    return dict(
        classe="mao",
        landmarks=pontos,
        x_min=min(x for x, _ in pontos),
        y_min=min(y for _, y in pontos),
        x_max=max(x for x, _ in pontos),
        y_max=max(y for _, y in pontos),
    )


def _area_caixa(caixa):
    largura = max(0, caixa["x_max"] - caixa["x_min"])
    altura = max(0, caixa["y_max"] - caixa["y_min"])
    return largura * altura


def iou(a, b):
    largura = max(0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
    altura = max(0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
    intersecao = largura * altura
    uniao = _area_caixa(a) + _area_caixa(b) - intersecao
    return intersecao / uniao if uniao > 0 else 0.0


def center(box):
    return ((box["x_min"] + box["x_max"]) / 2, (box["y_min"] + box["y_max"]) / 2)


class RastreadorObjetos:
    def __init__(self, ttl=0.6):
        self.ttl = ttl
        self.tracks = {}
        self.next_id = 1

    def _listar_candidatos(self, deteccoes):
        candidatos = []
        for indice, deteccao in enumerate(deteccoes):
            for identificador, (anterior, _) in self.tracks.items():
                if anterior["classe"] != deteccao["classe"]:
                    continue
                sobreposicao = iou(anterior, deteccao)
                escala = max(1, hypot(anterior["x_max"] - anterior["x_min"], anterior["y_max"] - anterior["y_min"]))
                distancia = hypot(*(a - b for a, b in zip(center(anterior), center(deteccao)))) / escala
                if sobreposicao >= 0.1 or distancia <= 0.5:
                    candidatos.append((sobreposicao - distancia, identificador, indice))
        return candidatos

    def atualizar(self, detections, timestamp):
        self.tracks = {
            identificador: registro
            for identificador, registro in self.tracks.items()
            if timestamp - registro[1] <= self.ttl
        }
        candidatos = self._listar_candidatos(detections)
        associacoes, identificadores_usados = {}, set()
        for _, identificador, indice in sorted(candidatos, reverse=True):
            if indice not in associacoes and identificador not in identificadores_usados:
                associacoes[indice] = identificador
                identificadores_usados.add(identificador)
        resultado = []
        for indice, deteccao in enumerate(detections):
            identificador = associacoes.get(indice)
            if identificador is None:
                identificador = self.next_id
                self.next_id += 1
            item = dict(deteccao, track_id=identificador)
            self.tracks[identificador] = (item, timestamp)
            resultado.append(item)
        return resultado


def _segmento_intercepta_caixa(a, b, caixa, margem):
    inicio, fim = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in (
        (-dx, a[0] - caixa["x_min"] + margem),
        (dx, caixa["x_max"] + margem - a[0]),
        (-dy, a[1] - caixa["y_min"] + margem),
        (dy, caixa["y_max"] + margem - a[1]),
    ):
        if p == 0:
            if q < 0:
                return False
        elif p < 0:
            inicio = max(inicio, q / p)
        else:
            fim = min(fim, q / p)
        if inicio > fim:
            return False
    return True


def verificar_contato(mao, produto, confirmado=False):
    pontos = mao.get("landmarks")
    if isinstance(pontos, (list, tuple)) and len(pontos) == 21:
        escala = max(1.0, hypot(pontos[0][0] - pontos[9][0], pontos[0][1] - pontos[9][1]))
        margem = settings.HAND_CONTACT_MARGIN * escala * (1.5 if confirmado else 1)
        indices_pontos = [
            indice
            for indice, ponto in enumerate(pontos)
            if _segmento_intercepta_caixa(ponto, ponto, produto, margem)
        ]
        segmentos = [
            (a, b)
            for a, b in HAND_CONNECTIONS
            if _segmento_intercepta_caixa(pontos[a], pontos[b], produto, margem)
        ]
        centro_palma = tuple(sum(pontos[i][eixo] for i in (0, 5, 9, 13, 17)) / 5 for eixo in (0, 1))
        palma_em_contato = _segmento_intercepta_caixa(centro_palma, centro_palma, produto, margem)
        return bool(indices_pontos or segmentos or palma_em_contato), indices_pontos, "landmarks"
    limiar = settings.IOU_THRESHOLD * (0.7 if confirmado else 1)
    sobreposicao = iou(mao, produto)
    return sobreposicao >= limiar and sobreposicao > 0, [], "iou"


def _interpretar_movimento(historico, mao):
    if len(historico) < 3:
        return "contato_provavel"
    _, mao_inicial, produto_inicial = historico[0]
    _, mao_final, produto_final = historico[-1]
    vetor_mao = tuple(b - a for a, b in zip(mao_inicial, mao_final))
    vetor_produto = tuple(b - a for a, b in zip(produto_inicial, produto_final))
    deslocamento_mao, deslocamento_produto = hypot(*vetor_mao), hypot(*vetor_produto)
    escala = max(1.0, hypot(mao["x_max"] - mao["x_min"], mao["y_max"] - mao["y_min"]))
    minimo = max(3.0, settings.INTERACTION_MOTION_MIN_RATIO * escala)
    if min(deslocamento_mao, deslocamento_produto) < minimo:
        return "contato_provavel"
    cosseno = sum(a * b for a, b in zip(vetor_mao, vetor_produto)) / (deslocamento_mao * deslocamento_produto)
    proporcao = min(deslocamento_mao, deslocamento_produto) / max(deslocamento_mao, deslocamento_produto)
    return "manipulacao_provavel" if cosseno >= 0.8 and proporcao >= 0.5 else "contato_provavel"


class ServicoEventos:
    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.tracker = RastreadorObjetos(settings.INTERACTION_RELEASE_SECONDS)
        self.pairs = {}
        self.last_timestamp = None
        self.detections = []
        self.diagnostics = []

    def _atualizar_contato(self, par, mao, produto, timestamp):
        intervalo = timestamp - par["last_seen"]
        if not par["confirmed"]:
            if par["consecutive"] and intervalo <= settings.INTERACTION_MAX_GAP_SECONDS:
                par["duration"] += intervalo
            else:
                par["duration"] = 0.0
                par["samples"] = 0
            par["samples"] += 1
        if not par["consecutive"] or intervalo > settings.INTERACTION_MAX_GAP_SECONDS:
            par["motion"].clear()
        par["motion"].append((timestamp, center(mao), center(produto)))
        while par["motion"] and timestamp - par["motion"][0][0] > JANELA_MOVIMENTO_SEGUNDOS:
            par["motion"].popleft()
        interpretacao = _interpretar_movimento(par["motion"], mao)
        par["last_seen"] = timestamp
        par["consecutive"] = True
        return interpretacao

    def _processar_par(self, mao, produto, timestamp, pares_observados, eventos):
        chave = (mao["track_id"], produto["track_id"])
        par = self.pairs.get(chave)
        confirmado = par is not None and par["confirmed"]
        em_contato, indices_pontos, metodo = verificar_contato(mao, produto, confirmado)
        if not em_contato:
            return
        pares_observados.add(chave)
        if par is None:
            par = dict(
                last_seen=timestamp,
                duration=0.0,
                samples=0,
                confirmed=False,
                consecutive=False,
                motion=deque(maxlen=120),
            )
            self.pairs[chave] = par
        interpretacao = self._atualizar_contato(par, mao, produto, timestamp)
        if (
            not par["confirmed"]
            and par["duration"] + TOLERANCIA_TEMPO_SEGUNDOS >= settings.INTERACTION_CONFIRM_SECONDS
            and par["samples"] >= settings.INTERACTION_MIN_SAMPLES
        ):
            par["confirmed"] = True
            eventos.append(
                dict(
                    tipo="interacao_mao",
                    produto=produto["classe"],
                    quantidade=1,
                    mao_id=chave[0],
                    produto_id=chave[1],
                    pontos_mao=indices_pontos,
                    metodo=metodo,
                    interpretacao=interpretacao,
                )
            )
        self.diagnostics.append(
            dict(
                mao_id=chave[0],
                produto_id=chave[1],
                pontos_mao=indices_pontos,
                interpretacao=interpretacao,
                estado="confirmada" if par["confirmed"] else "candidata",
            )
        )

    def processar(self, df_atual, timestamp=None):
        timestamp = time.monotonic() if timestamp is None else timestamp
        if self.last_timestamp is not None and (
            timestamp <= self.last_timestamp
            or timestamp - self.last_timestamp > settings.INTERACTION_RESET_SECONDS
        ):
            self.reiniciar()
        self.last_timestamp = timestamp
        self.detections = self.tracker.atualizar(df_atual.to_dict("records"), timestamp)
        self.pairs = {
            chave: valor
            for chave, valor in self.pairs.items()
            if timestamp - valor["last_seen"] <= settings.INTERACTION_RELEASE_SECONDS
        }
        maos = [item for item in self.detections if item["classe"] == "mao"]
        produtos = [item for item in self.detections if item["classe"] != "mao"]
        eventos, pares_observados = [], set()
        self.diagnostics = []
        for mao in maos:
            for produto in produtos:
                self._processar_par(mao, produto, timestamp, pares_observados, eventos)
        for chave, par in self.pairs.items():
            if chave not in pares_observados:
                par["consecutive"] = False
        return eventos


class ServicoVisao:
    def __init__(self, caminho_pesos=None, device=None):
        self.predict_options = {} if device is None else {"device": device}
        self.model_path = str(Path(caminho_pesos or settings.MODEL_PATH).resolve())
        if not Path(self.model_path).is_file():
            raise FileNotFoundError(f"Pesos ausentes para {settings.MODELO_ATIVO}: {self.model_path}")
        self.modelo = YOLO(self.model_path)
        self.classes = dict(self.modelo.names)
        classes_esperadas = settings.EXTERNAL_CLASSES if settings.USE_EXTERNAL_VALIDATION_DATASET else settings.CLASSES
        if self.classes != dict(enumerate(classes_esperadas)):
            raise ValueError(f"Classes dos pesos incompativeis: {self.classes}; esperado {classes_esperadas}")
        self.model_name = settings.MODELO_ATIVO if caminho_pesos is None else Path(caminho_pesos).parent.name
        print(f"[VISAO] Modelo: {self.model_name}; pesos: {self.model_path}")
        self.modelo(np.zeros((480, 640, 3), dtype=np.uint8), verbose=False, **self.predict_options)
        self.hands = ServicoMaos() if settings.HAND_LANDMARKS_ENABLED else None

    def fechar(self):
        if self.hands is not None:
            self.hands.close()

    def processar_frame(self, frame, timestamp=None):
        timestamp = time.monotonic() if timestamp is None else timestamp
        resultados = self.modelo(frame, verbose=False, **self.predict_options)[0]
        deteccoes = []
        for caixa in resultados.boxes:
            x_min, y_min, x_max, y_max = caixa.xyxy[0].tolist()
            classe_id = int(caixa.cls[0])
            if classe_id < 0 or classe_id >= len(self.classes):
                continue
            if self.hands is not None and self.classes[classe_id] == "mao":
                continue
            deteccoes.append(
                {
                    "classe": self.classes[classe_id],
                    "confianca": float(caixa.conf[0]),
                    "x_min": x_min,
                    "y_min": y_min,
                    "x_max": x_max,
                    "y_max": y_max,
                }
            )
        if self.hands is not None:
            deteccoes.extend(self.hands.processar_frame(frame, timestamp))
        tabela_deteccoes = pd.DataFrame(deteccoes)
        tabela_deteccoes.attrs["timestamp"] = timestamp
        return tabela_deteccoes


def enviar_evento_para_api(evento):
    corpo = json.dumps(evento).encode("utf-8")
    requisicao = urllib.request.Request(
        settings.API_ENDPOINT,
        data=corpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(requisicao, timeout=5):
        pass


def iniciar_monitoramento():
    visao = ServicoVisao()
    eventos = ServicoEventos()
    ultimo_processamento = 0.0
    quadros = gerador_de_frames(settings.ESP32_STREAM_URL)

    try:
        for imagem in quadros:
            agora = time.monotonic()
            if agora - ultimo_processamento < settings.INTERVALO_PROCESSAMENTO:
                continue

            deteccoes = visao.processar_frame(imagem, timestamp=agora)
            novos_eventos = eventos.processar(deteccoes, deteccoes.attrs.get("timestamp", agora))
            for evento in novos_eventos:
                try:
                    enviar_evento_para_api(evento)
                    print(f"[API] Evento enviado: {evento['tipo']} -> {evento['produto']}")
                except Exception as erro:
                    print(f"[API_ERRO] Falha ao enviar evento: {erro}")

            ultimo_processamento = agora
    finally:
        quadros.close()
        visao.fechar()


if __name__ == "__main__":
    iniciar_monitoramento()