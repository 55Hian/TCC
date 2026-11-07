"""Acesso PostgreSQL ao esquema completo da 2.0.0."""
import json
from datetime import timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from config import DATABASE_URL

SCHEMA = Path(__file__).resolve().parents[1] / "database" / "schema.sql"


def conectar():
    return psycopg.connect(DATABASE_URL, connect_timeout=4, row_factory=dict_row)


def inicializar():
    comandos = SCHEMA.read_text(encoding="utf-8-sig").split(";")
    with conectar() as banco:
        for comando in comandos:
            if comando.strip():
                banco.execute(comando)


def salvar_interacao(evento, momento):
    momento = momento.astimezone(timezone.utc).replace(tzinfo=None)
    pontos = json.dumps(evento["pontos_mao"]) if evento.get("pontos_mao") is not None else None
    with conectar() as banco:
        produto = banco.execute(
            "SELECT id_produto, nome FROM produto WHERE classe_modelo=%s AND ativo=TRUE",
            (evento["produto"],),
        ).fetchone()
        produto_id = evento.get("produto_id") or (produto["id_produto"] if produto else None)
        nome_produto = produto["nome"] if produto else evento["produto"]
        return banco.execute(
            """INSERT INTO evento
               (tipo, produto, quantidade, mao_id, produto_id, pontos_mao, metodo, interpretacao, data_inc)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id_event AS id, tipo, produto, quantidade, mao_id, produto_id,
                         pontos_mao, metodo, interpretacao, data_inc AS momento,
                         video_path, video_status""",
            (evento["tipo"], nome_produto, evento.get("quantidade", 1),
             evento.get("mao_id"), produto_id, pontos,
             evento.get("metodo"), evento.get("interpretacao"), momento),
        ).fetchone()


def listar_interacoes(limite=200):
    with conectar() as banco:
        return banco.execute(
            """SELECT id_event AS id, tipo, produto, quantidade, mao_id, produto_id,
                      pontos_mao, metodo, interpretacao, data_inc AS momento,
                      video_path, video_status
               FROM (SELECT * FROM evento ORDER BY id_event DESC LIMIT %s) recentes
               ORDER BY id_event ASC""",
            (limite,),
        ).fetchall()


def salvar_variacao(variacao_peso, momento):
    momento = momento.astimezone(timezone.utc).replace(tzinfo=None)
    with conectar() as banco:
        return banco.execute(
            """INSERT INTO variacao_balanca (variacao_peso, momento)
               VALUES (%s, %s) RETURNING id_variacao AS id, variacao_peso, momento""",
            (variacao_peso, momento),
        ).fetchone()


def listar_variacoes(limite=200):
    with conectar() as banco:
        return banco.execute(
            """SELECT id_variacao AS id, variacao_peso, momento
               FROM variacao_balanca ORDER BY momento DESC LIMIT %s""",
            (limite,),
        ).fetchall()


def atualizar_video_evento(id_evento, caminho, status):
    with conectar() as banco:
        banco.execute(
            "UPDATE evento SET video_path=%s, video_status=%s WHERE id_event=%s",
            (caminho, status, id_evento),
        )
        banco.execute(
            "UPDATE correlacao_retirada SET video_path=%s, video_status=%s WHERE id_event=%s",
            (caminho, status, id_evento),
        )


def marcar_video_agendado(id_evento):
    with conectar() as banco:
        banco.execute(
            "UPDATE evento SET video_status='agendada' WHERE id_event=%s AND video_status='nao_solicitado'",
            (id_evento,),
        )
        banco.execute(
            "UPDATE correlacao_retirada SET video_status='agendada' WHERE id_event=%s AND video_status='nao_solicitado'",
            (id_evento,),
        )


def caminho_video_evento(id_evento):
    registro = status_video_evento(id_evento)
    return registro["video_path"] if registro else None


def status_video_evento(id_evento):
    with conectar() as banco:
        registro = banco.execute(
            "SELECT video_path, video_status FROM evento WHERE id_event=%s", (id_evento,)
        ).fetchone()
        return registro


def listar_produtos():
    with conectar() as banco:
        return banco.execute(
            """SELECT id_produto AS id, nome, classe_modelo, peso, descricao, ativo,
                      criado_em, atualizado_em
               FROM produto ORDER BY nome, id_produto"""
        ).fetchall()


def criar_produto(produto):
    with conectar() as banco:
        return banco.execute(
            """INSERT INTO produto (nome, classe_modelo, peso, descricao, ativo)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id_produto AS id, nome, classe_modelo, peso, descricao, ativo,
                         criado_em, atualizado_em""",
            (produto["nome"], produto["classe_modelo"], produto["peso"],
             produto["descricao"], produto["ativo"]),
        ).fetchone()


def atualizar_produto(id_produto, produto):
    with conectar() as banco:
        return banco.execute(
            """UPDATE produto SET nome=%s, classe_modelo=%s, peso=%s, descricao=%s,
                      ativo=%s, atualizado_em=CURRENT_TIMESTAMP
               WHERE id_produto=%s
               RETURNING id_produto AS id, nome, classe_modelo, peso, descricao, ativo,
                         criado_em, atualizado_em""",
            (produto["nome"], produto["classe_modelo"], produto["peso"], produto["descricao"],
             produto["ativo"], id_produto),
        ).fetchone()


def remover_produto(id_produto):
    with conectar() as banco:
        banco.execute("UPDATE evento SET produto_id=NULL WHERE produto_id=%s", (id_produto,))
        resultado = banco.execute(
            "DELETE FROM produto WHERE id_produto=%s RETURNING id_produto", (id_produto,)
        ).fetchone()
        return resultado is not None
