"""Consulta o catálogo de imagens sem iniciar captura ou alterar arquivos."""
import os


def _extensao_valida(nome):
    return nome.lower().endswith((".jpg", ".jpeg", ".png"))


def listar_imagens(pasta, pasta_anotacoes):
    if not os.path.isdir(pasta):
        return {"imagens": []}

    imagens = []
    for nome in sorted(os.listdir(pasta)):
        caminho = os.path.join(pasta, nome)
        if not _extensao_valida(nome) or not os.path.isfile(caminho):
            continue
        nome_base = os.path.splitext(nome)[0]
        anotado = os.path.isfile(os.path.join(pasta_anotacoes, f"{nome_base}.json"))
        imagens.append({"nome": nome, "anotado": anotado, "versao": str(os.stat(caminho).st_mtime_ns)})
    return {"imagens": imagens}


