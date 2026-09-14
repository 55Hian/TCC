"""Associacao espacial de curto prazo, por classe, sem alterar o modelo YOLO."""
from math import hypot


def _area_caixa(caixa):
    """Calcula a área, tratando dimensões negativas como área zero."""
    largura = max(0, caixa["x_max"] - caixa["x_min"])
    altura = max(0, caixa["y_max"] - caixa["y_min"])
    return largura * altura


def iou(a, b):
    """Mede a sobreposição: área da interseção dividida pela área da união."""
    largura = max(0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
    altura = max(0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
    intersecao = largura * altura
    uniao = _area_caixa(a) + _area_caixa(b) - intersecao
    return intersecao / uniao if uniao > 0 else 0.0


def center(box):
    return ((box["x_min"] + box["x_max"]) / 2, (box["y_min"] + box["y_max"]) / 2)


class RastreadorObjetos:
    """IDs locais a uma sessao; nao garante identidade apos oclusoes/cruzamentos."""
    def __init__(self, ttl=0.6):
        self.ttl = ttl
        self.tracks = {}
        self.next_id = 1

    def _listar_candidatos(self, deteccoes):
        """Pontua somente objetos da mesma classe próximos ou sobrepostos."""
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
        """Associa detecções da mesma classe e atribui IDs aos novos objetos."""
        # Descarta objetos ausentes por mais tempo que a tolerância da sessão.
        self.tracks = {identificador: registro for identificador, registro in self.tracks.items()
                       if timestamp - registro[1] <= self.ttl}
        candidatos = self._listar_candidatos(detections)
        associacoes, identificadores_usados = {}, set()
        # Prioriza a melhor combinação; cada objeto e detecção participam uma única vez.
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

    # Compatibilidade com consumidores anteriores.
    update = atualizar


# Compatibilidade de importação com os nomes anteriores.
ObjectTracker = RastreadorObjetos
