"""Dispara um evento quando os landmarks tocam uma caixa por tempo suficiente."""
from datetime import datetime, timezone


class ConfirmadorInteracoes:
    def __init__(self, duracao=0.3):
        self.duracao = duracao
        self.contatos = {}

    def atualizar(self, maos, produtos, agora):
        vistos = set()
        eventos = []
        for indice_mao, mao in enumerate(maos):
            centro_mao = mao[0]
            for produto in produtos:
                x1, y1, x2, y2 = produto["caixa"]
                pontos = [p for p in mao if x1 <= p[0] <= x2 and y1 <= p[1] <= y2]
                if not pontos:
                    continue
                chave = (indice_mao, produto["classe"], x1 // 80, y1 // 80)
                vistos.add(chave)
                contato = self.contatos.setdefault(chave, {"inicio": agora, "enviado": False})
                if not contato["enviado"] and agora - contato["inicio"] >= self.duracao:
                    contato["enviado"] = True
                    eventos.append({"tipo": "interacao_mao", "produto": produto["classe"], "quantidade": 1, "timestamp": datetime.now(timezone.utc).isoformat()})
        self.contatos = {chave: valor for chave, valor in self.contatos.items() if chave in vistos}
        return eventos


