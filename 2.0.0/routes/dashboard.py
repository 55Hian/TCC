"""Dados resumidos para o painel inicial."""
import psycopg
from fastapi import APIRouter, HTTPException

from config import modelo_ativo
from services.database import conectar

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def consultar_painel():
    try:
        with conectar() as banco:
            resumo = banco.execute(
                """SELECT
                     (SELECT count(*) FROM evento WHERE tipo = 'interacao_mao' AND data_inc >= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - INTERVAL '24 hours') AS interacoes_24h,
                     (SELECT count(*) FROM variacao_balanca WHERE momento >= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - INTERVAL '24 hours') AS variacoes_24h,
                     (SELECT count(*) FROM correlacao_retirada WHERE criada_em >= CURRENT_TIMESTAMP - INTERVAL '24 hours') AS correlacoes_24h,
                     (SELECT count(*) FROM evento e WHERE e.video_status IN ('nao_solicitado', 'agendada', 'erro')
                       AND EXISTS (SELECT 1 FROM correlacao_retirada c WHERE c.id_event = e.id_event)) AS clipes_pendentes_ou_com_erro"""
            ).fetchone()
            eventos = banco.execute(
                """SELECT id_event AS id, produto, produto_id,
                          data_inc AT TIME ZONE 'UTC' AS timestamp
                   FROM evento WHERE tipo = 'interacao_mao'
                   ORDER BY data_inc DESC, id_event DESC LIMIT 8"""
            ).fetchall()
            balanca = banco.execute(
                """SELECT id_variacao AS id, variacao_peso,
                          momento AT TIME ZONE 'UTC' AS timestamp
                   FROM variacao_balanca ORDER BY momento DESC, id_variacao DESC LIMIT 8"""
            ).fetchall()
            correlacoes = banco.execute(
                """SELECT c.id_retirada, c.id_event, c.id_produto, c.nome_produto,
                          c.peso_produto, c.timestamp_camera, c.timestamp_balanca,
                          c.video_path, c.video_status
                   FROM correlacao_retirada c
                   LEFT JOIN evento e ON e.id_event = c.id_event
                   ORDER BY c.criada_em DESC, c.id_retirada DESC LIMIT 8"""
            ).fetchall()
        for item in correlacoes:
            item["video_url"] = (
                f"/api/camera-secundaria/gravacoes/{item['id_event']}/arquivo"
                if item["video_status"] == "concluida" and item["video_path"] else None
            )
        return {
            "resumo": resumo,
            "eventos": eventos,
            "balanca": balanca,
            "correlacoes": correlacoes,
            "modelo_ativo": modelo_ativo(),
        }
    except psycopg.Error as erro:
        raise HTTPException(status_code=503, detail="Banco indisponivel; painel nao pode ser atualizado") from erro
