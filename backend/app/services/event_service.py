"""Interacoes provaveis por par mao-produto, com confirmacao temporal."""
from collections import deque
from math import hypot
import time

from core.config import settings
from services.hand_service import HAND_CONNECTIONS
from services.tracking_service import RastreadorObjetos, center, iou

calcular_area_intersecao = iou

JANELA_MOVIMENTO_SEGUNDOS = 0.6
TOLERANCIA_TEMPO_SEGUNDOS = 1e-9


def _segmento_intercepta_caixa(a, b, caixa, margem):
    # Liang-Barsky: intersecao do segmento com o retangulo expandido.
    inicio, fim = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - caixa["x_min"] + margem),
                 (dx, caixa["x_max"] + margem - a[0]),
                 (-dy, a[1] - caixa["y_min"] + margem),
                 (dy, caixa["y_max"] + margem - a[1])):
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
    """Verifica pontos e segmentos da mão; usa IoU quando não há landmarks."""
    # Após a confirmação, a margem maior tolera pequenas oscilações da detecção.
    pontos = mao.get("landmarks")
    if isinstance(pontos, (list, tuple)) and len(pontos) == 21:
        escala = max(1.0, hypot(pontos[0][0] - pontos[9][0], pontos[0][1] - pontos[9][1]))
        margem = settings.HAND_CONTACT_MARGIN * escala * (1.5 if confirmado else 1)
        indices_pontos = [indice for indice, ponto in enumerate(pontos)
                 if _segmento_intercepta_caixa(ponto, ponto, produto, margem)]
        segmentos = [(a, b) for a, b in HAND_CONNECTIONS
                    if _segmento_intercepta_caixa(pontos[a], pontos[b], produto, margem)]
        centro_palma = tuple(sum(pontos[i][eixo] for i in (0, 5, 9, 13, 17)) / 5 for eixo in (0, 1))
        palma_em_contato = _segmento_intercepta_caixa(centro_palma, centro_palma, produto, margem)
        return bool(indices_pontos or segmentos or palma_em_contato), indices_pontos, "landmarks"
    limiar = settings.IOU_THRESHOLD * (0.7 if confirmado else 1)
    sobreposicao = iou(mao, produto)
    return sobreposicao >= limiar and sobreposicao > 0, [], "iou"


def gerar_eventos(df_atual):
    """Compatibilidade: candidatos de um frame, sem confirmacao temporal.

    Monitoramento e CLI usam EventService. Esta funcao nao deve publicar eventos.
    """
    registros = df_atual.to_dict("records")
    return [dict(tipo="interacao_mao", produto=produto["classe"], quantidade=1)
            for produto in registros if produto["classe"] != "mao"
            if any(verificar_contato(mao, produto)[0] for mao in registros if mao["classe"] == "mao")]


def _interpretar_movimento(historico, mao):
    """Distingue contato de deslocamento conjunto da mão e do produto."""
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
        """Acumula apenas contato contínuo e mantém uma janela curta de movimento."""
        # Lacunas não contam como contato e reiniciam candidatos ainda não confirmados.
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
        """Atualiza um par e registra sua confirmação e diagnóstico."""
        chave = (mao["track_id"], produto["track_id"])
        par = self.pairs.get(chave)
        confirmado = par is not None and par["confirmed"]
        em_contato, indices_pontos, metodo = verificar_contato(mao, produto, confirmado)
        if not em_contato:
            return
        pares_observados.add(chave)
        if par is None:
            par = dict(last_seen=timestamp, duration=0.0, samples=0, confirmed=False,
                            consecutive=False, motion=deque(maxlen=120))
            self.pairs[chave] = par
        interpretacao = self._atualizar_contato(par, mao, produto, timestamp)
        if (not par["confirmed"]
                and par["duration"] + TOLERANCIA_TEMPO_SEGUNDOS >= settings.INTERACTION_CONFIRM_SECONDS
                and par["samples"] >= settings.INTERACTION_MIN_SAMPLES):
            # Um par confirmado só pode gerar outro evento depois de expirar.
            par["confirmed"] = True
            eventos.append(dict(
                tipo="interacao_mao", produto=produto["classe"], quantidade=1,
                mao_id=chave[0], produto_id=chave[1], pontos_mao=indices_pontos,
                metodo=metodo, interpretacao=interpretacao,
            ))
        self.diagnostics.append(dict(
            mao_id=chave[0], produto_id=chave[1], pontos_mao=indices_pontos,
            interpretacao=interpretacao,
            estado="confirmada" if par["confirmed"] else "candidata",
        ))

    def processar(self, df_atual, timestamp=None):
        """Rastreia pares mão-produto e emite um evento por contato confirmado."""
        # Relógio regressivo ou pausa longa invalidam a continuidade da sessão.
        timestamp = time.monotonic() if timestamp is None else timestamp
        if self.last_timestamp is not None and (
                timestamp <= self.last_timestamp or
                timestamp - self.last_timestamp > settings.INTERACTION_RESET_SECONDS):
            self.reiniciar()
        self.last_timestamp = timestamp
        self.detections = self.tracker.atualizar(df_atual.to_dict("records"), timestamp)
        self.pairs = {chave: valor for chave, valor in self.pairs.items()
                      if timestamp - valor["last_seen"] <= settings.INTERACTION_RELEASE_SECONDS}
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

    # Compatibilidade com consumidores anteriores.
    reset = reiniciar


def contact(hand, product, active=False):
    """Mantém a assinatura usada por integrações anteriores."""
    return verificar_contato(hand, product, active)


# Compatibilidade de importação com os nomes anteriores.
EventService = ServicoEventos
