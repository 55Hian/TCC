"""Consulta e administracao das tabelas do banco da aplicacao."""
import json
from datetime import datetime, timezone

import psycopg
from fastapi import APIRouter, Body, HTTPException, Query, Response
from psycopg import sql

from services.database import conectar

router = APIRouter(prefix="/api/banco", tags=["banco"])


def campo(nome, rotulo, tipo="text", obrigatorio=False, padrao=None, editavel=True):
    return {"nome": nome, "rotulo": rotulo, "tipo": tipo,
            "obrigatorio": obrigatorio, "padrao": padrao, "editavel": editavel}


TABELAS = {
    "usuarios": {"tabela": "usuario", "chave": "id_morador", "rotulo": "Usuarios", "campos": [
        campo("nome", "Nome", obrigatorio=True), campo("status_ativo", "Ativo", "boolean", padrao=True),
        campo("vetor_facial", "Vetor facial (JSON)", "vector")]},
    "sessoes-tracking": {"tabela": "sessoes_tracking", "chave": "id_sessao", "rotulo": "Sessoes de tracking", "campos": [
        campo("id_morador", "ID do usuario", "integer"), campo("track_id", "Track ID", "integer", True),
        campo("entrada", "Entrada", "datetime"), campo("saida", "Saida", "datetime")]},
    "sessoes-compra": {"tabela": "sessoes_compra", "chave": "id_sessao", "rotulo": "Sessoes de compra", "campos": [
        campo("id_morador", "ID do usuario", "integer", True), campo("inicio_sessao", "Inicio", "datetime"),
        campo("fim_sessao", "Fim", "datetime"), campo("status", "Status", padrao="EM_ANDAMENTO", obrigatorio=True),
        campo("track_id_atual", "Track ID atual", "integer")]},
    "eventos": {"tabela": "evento", "chave": "id_event", "rotulo": "Eventos da camera", "campos": [
        campo("tipo", "Tipo", obrigatorio=True), campo("produto", "Produto", obrigatorio=True),
        campo("quantidade", "Quantidade", "integer", True, 1), campo("mao_id", "ID da mao", "integer"),
        campo("produto_id", "ID do produto", "integer"), campo("pontos_mao", "Pontos da mao (JSON/texto)"),
        campo("metodo", "Metodo"), campo("interpretacao", "Interpretacao"), campo("data_inc", "Data", "timestamp"),
        campo("video_path", "Caminho do video"), campo("video_status", "Status do video", padrao="nao_solicitado")]},
    "variacoes-balanca": {"tabela": "variacao_balanca", "chave": "id_variacao", "rotulo": "Variacoes da balanca", "campos": [
        campo("variacao_peso", "Variacao de peso", "number", True), campo("momento", "Timestamp", "timestamp")]},
    "correlacoes": {"tabela": "correlacao_retirada", "chave": "id_retirada", "rotulo": "Correlacoes de retirada", "campos": [
        campo("id_event", "ID do evento", "integer", True), campo("id_variacao", "ID da variacao", "integer", True),
        campo("id_produto", "ID do produto", "integer"), campo("nome_produto", "Nome do produto"),
        campo("peso_produto", "Peso do produto", "number"),
        campo("timestamp_camera", "Timestamp da camera", "datetime"),
        campo("timestamp_balanca", "Timestamp da balanca", "datetime"),
        campo("video_path", "Caminho do video", editavel=False),
        campo("video_status", "Estado do video", padrao="nao_solicitado", editavel=False),
        campo("momento_retirada", "Momento da retirada", "datetime", True),
        campo("estado", "Estado", obrigatorio=True, padrao="confirmada"),
        campo("criada_em", "Criada em", "datetime", editavel=False)]},
}


def configurar(tabela):
    config = TABELAS.get(tabela)
    if config is None:
        raise HTTPException(status_code=404, detail="Tabela desconhecida")
    return config


def converter(config, dados, criar=False):
    campos = {item["nome"]: item for item in config["campos"] if item["editavel"]}
    desconhecidos = set(dados) - set(campos)
    if desconhecidos:
        raise HTTPException(status_code=422, detail="Campo nao permitido: " + ", ".join(sorted(desconhecidos)))
    valores = {}
    for nome, valor in dados.items():
        definicao = campos[nome]
        if valor is None or valor == "":
            if definicao["obrigatorio"] and criar:
                raise HTTPException(status_code=422, detail=f"{definicao['rotulo']} e obrigatorio")
            valores[nome] = None
            continue
        tipo = definicao["tipo"]
        try:
            if tipo == "integer":
                valores[nome] = int(valor)
            elif tipo == "number":
                valores[nome] = float(valor)
            elif tipo == "boolean":
                valores[nome] = valor if isinstance(valor, bool) else str(valor).lower() in ("true", "1", "sim")
            elif tipo in ("datetime", "timestamp"):
                momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
                valores[nome] = momento.astimezone(timezone.utc).replace(tzinfo=None) if tipo == "timestamp" and momento.tzinfo else momento
            elif tipo == "vector":
                vetor = json.loads(valor) if isinstance(valor, str) else valor
                if not isinstance(vetor, list) or len(vetor) != 128:
                    raise ValueError
                valores[nome] = "[" + ",".join(str(float(item)) for item in vetor) + "]"
            else:
                valores[nome] = str(valor).strip()
        except (TypeError, ValueError, json.JSONDecodeError) as erro:
            raise HTTPException(status_code=422, detail=f"Valor invalido para {definicao['rotulo']}") from erro
    if criar:
        for definicao in config["campos"]:
            nome = definicao["nome"]
            if definicao["obrigatorio"] and nome not in valores and definicao["padrao"] is None:
                raise HTTPException(status_code=422, detail=f"{definicao['rotulo']} e obrigatorio")
            if nome not in valores and definicao["padrao"] is not None:
                valores[nome] = definicao["padrao"]
    return valores


def mapear_erro(erro):
    if isinstance(erro, psycopg.errors.UniqueViolation):
        raise HTTPException(status_code=409, detail="Registro duplicado") from erro
    if isinstance(erro, (psycopg.errors.ForeignKeyViolation, psycopg.errors.NotNullViolation)):
        raise HTTPException(status_code=409, detail="Registro relacionado impede essa operacao") from erro
    raise HTTPException(status_code=503, detail="Banco indisponivel ou operacao recusada") from erro


def campos_select(config):
    nomes = [config["chave"]] + [item["nome"] for item in config["campos"]]
    return sql.SQL(", ").join(
        sql.SQL("{}::text AS {}").format(sql.Identifier(nome), sql.Identifier(nome))
        if nome == "vetor_facial" else sql.Identifier(nome) for nome in nomes
    )


def normalizar_registro(config, registro):
    for definicao in config["campos"]:
        nome = definicao["nome"]
        valor = registro.get(nome)
        if definicao["tipo"] == "timestamp" and isinstance(valor, datetime) and valor.tzinfo is None:
            registro[nome] = valor.replace(tzinfo=timezone.utc)
    return registro


@router.get("/tabelas")
def listar_tabelas():
    return {"tabelas": [{"nome": nome, "rotulo": conf["rotulo"], "chave": conf["chave"], "campos": conf["campos"]}
                        for nome, conf in TABELAS.items()]}


@router.get("/{tabela}")
def listar_registros(tabela: str, limite: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    config = configurar(tabela)
    try:
        with conectar() as banco:
            registros = banco.execute(sql.SQL("SELECT {} FROM {} ORDER BY {} DESC LIMIT %s OFFSET %s").format(
                campos_select(config), sql.Identifier(config["tabela"]), sql.Identifier(config["chave"])),
                (limite, offset)).fetchall()
            total = banco.execute(sql.SQL("SELECT count(*) AS total FROM {}").format(
                sql.Identifier(config["tabela"]))).fetchone()["total"]
        return {"registros": [normalizar_registro(config, item) for item in registros],
                "total": total, "limite": limite, "offset": offset}
    except psycopg.Error as erro:
        mapear_erro(erro)


@router.post("/{tabela}", status_code=201)
def criar_registro(tabela: str, dados: dict = Body(...)):
    config = configurar(tabela)
    valores = converter(config, dados, criar=True)
    nomes = list(valores)
    placeholders = [sql.SQL("%s::vector") if nome == "vetor_facial" else sql.SQL("%s") for nome in nomes]
    try:
        with conectar() as banco:
            registro = banco.execute(sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING {}").format(
                sql.Identifier(config["tabela"]), sql.SQL(", ").join(map(sql.Identifier, nomes)),
                sql.SQL(", ").join(placeholders), campos_select(config)),
                tuple(valores[nome] for nome in nomes)).fetchone()
        return normalizar_registro(config, registro)
    except psycopg.Error as erro:
        mapear_erro(erro)


@router.put("/{tabela}/{id_registro}")
def atualizar_registro(tabela: str, id_registro: int, dados: dict = Body(...)):
    config = configurar(tabela)
    valores = converter(config, dados)
    if not valores:
        raise HTTPException(status_code=422, detail="Informe ao menos um campo")
    sets = [sql.SQL("{}=%s{}").format(sql.Identifier(nome), sql.SQL("::vector") if nome == "vetor_facial" else sql.SQL(""))
            for nome in valores]
    try:
        with conectar() as banco:
            registro = banco.execute(sql.SQL("UPDATE {} SET {} WHERE {}=%s RETURNING {}").format(
                sql.Identifier(config["tabela"]), sql.SQL(", ").join(sets),
                sql.Identifier(config["chave"]), campos_select(config)),
                tuple(valores.values()) + (id_registro,)).fetchone()
        if registro is None:
            raise HTTPException(status_code=404, detail="Registro nao encontrado")
        return normalizar_registro(config, registro)
    except psycopg.Error as erro:
        mapear_erro(erro)


@router.delete("/{tabela}/{id_registro}", status_code=204)
def remover_registro(tabela: str, id_registro: int):
    config = configurar(tabela)
    try:
        with conectar() as banco:
            removido = banco.execute(sql.SQL("DELETE FROM {} WHERE {}=%s RETURNING {}").format(
                sql.Identifier(config["tabela"]), sql.Identifier(config["chave"]),
                sql.Identifier(config["chave"])), (id_registro,)).fetchone()
        if removido is None:
            raise HTTPException(status_code=404, detail="Registro nao encontrado")
        return Response(status_code=204)
    except psycopg.Error as erro:
        mapear_erro(erro)
