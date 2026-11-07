"""Encontra pares entre interacoes da camera e retiradas registradas pela balanca."""
import logging
from datetime import datetime, timezone

from config import (
    CORRELATION_INTERVAL_SECONDS,
    CORRELATION_WEIGHT_TOLERANCE,
    CORRELATION_WINDOW_SECONDS,
    VIDEO_BUFFER_SECONDS,
)
from services.database import conectar, marcar_video_agendado, atualizar_video_evento
from services.camera_secundaria import camera_secundaria

logger = logging.getLogger(__name__)


def _carregar_candidatos(banco):
    """Busca pares dentro da janela no PostgreSQL e limita o lote por ciclo."""
    return banco.execute(
        """SELECT e.id_event, e.produto_id, p.nome AS nome_produto, p.peso,
                  e.data_inc, v.id_variacao, v.variacao_peso, v.momento,
                  abs(extract(epoch FROM (v.momento - e.data_inc))) AS diferenca_tempo,
                  abs(abs(v.variacao_peso) - p.peso) / p.peso AS diferenca_peso
           FROM evento e
           JOIN produto p ON p.id_produto = e.produto_id
           JOIN variacao_balanca v
             ON v.variacao_peso < 0
            AND v.momento BETWEEN e.data_inc - (%s * INTERVAL '1 second')
                              AND e.data_inc + (%s * INTERVAL '1 second')
            AND abs(abs(v.variacao_peso) - p.peso) <= p.peso * %s
           WHERE e.tipo = 'interacao_mao'
             AND NOT EXISTS (
                 SELECT 1 FROM correlacao_retirada c WHERE c.id_event = e.id_event
             )
             AND NOT EXISTS (
                 SELECT 1 FROM correlacao_retirada c WHERE c.id_variacao = v.id_variacao
             )
           ORDER BY diferenca_tempo, diferenca_peso, e.id_event, v.id_variacao
           LIMIT 1000""",
        (CORRELATION_WINDOW_SECONDS, CORRELATION_WINDOW_SECONDS,
         CORRELATION_WEIGHT_TOLERANCE),
    ).fetchall()


def correlacionar_pendentes():
    """Processa os dados persistidos; cada evento e variacao so entram uma vez."""
    with conectar() as banco:
        bloqueado = banco.execute("SELECT pg_try_advisory_xact_lock(2048002000) AS bloqueado").fetchone()
        if not bloqueado["bloqueado"]:
            return 0

        candidatos = _carregar_candidatos(banco)
        usados_eventos = set()
        usadas_variacoes = set()
        inseridas = 0
        for candidato in candidatos:
            if candidato["id_event"] in usados_eventos or candidato["id_variacao"] in usadas_variacoes:
                continue
            timestamp_camera = candidato["data_inc"].replace(tzinfo=timezone.utc)
            timestamp_balanca = candidato["momento"].replace(tzinfo=timezone.utc)
            registro = banco.execute(
                """INSERT INTO correlacao_retirada
                       (id_event, id_variacao, id_produto, nome_produto, peso_produto,
                        timestamp_camera, timestamp_balanca, momento_retirada, estado)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'confirmada')
                   ON CONFLICT (id_event, id_variacao) DO NOTHING
                   RETURNING id_retirada""",
                (candidato["id_event"], candidato["id_variacao"], candidato["produto_id"],
                 candidato["nome_produto"], candidato["peso"], timestamp_camera,
                 timestamp_balanca, timestamp_balanca),
            ).fetchone()
            if registro:
                usados_eventos.add(candidato["id_event"])
                usadas_variacoes.add(candidato["id_variacao"])
                inseridas += 1
        return inseridas


def agendar_videos_pendentes():
    """Pede um clipe para cada correlacao ainda sem gravacao agendada."""
    with conectar() as banco:
        pendentes = banco.execute(
            """SELECT c.id_event, c.timestamp_balanca
               FROM correlacao_retirada c
               JOIN evento e ON e.id_event = c.id_event
               WHERE e.video_status = 'nao_solicitado'
               ORDER BY c.criada_em, c.id_retirada
               LIMIT 50"""
        ).fetchall()

    agendados = 0
    for item in pendentes:
        timestamp = item["timestamp_balanca"]
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        idade = (datetime.now(timezone.utc) - timestamp).total_seconds()
        if idade > VIDEO_BUFFER_SECONDS:
            atualizar_video_evento(item["id_event"], None, "erro")
            logger.warning("Clipe do evento %s expirou antes de ser agendado", item["id_event"])
            continue
        try:
            camera_secundaria.agendar_gravacao(item["id_event"], timestamp)
        except (RuntimeError, ValueError) as erro:
            logger.info("Clipe do evento %s aguardando camera: %s", item["id_event"], erro)
            continue
        marcar_video_agendado(item["id_event"])
        agendados += 1
    return agendados


def executar_correlacao_periodica(parar):
    """Executa uma varredura imediata e repete no intervalo configurado."""
    while not parar.is_set():
        try:
            quantidade = correlacionar_pendentes()
            if quantidade:
                logger.info("Correlacoes de retirada criadas: %s", quantidade)
            agendados = agendar_videos_pendentes()
            if agendados:
                logger.info("Clipes de retirada agendados: %s", agendados)
        except Exception:
            logger.exception("Falha ao processar correlacoes de retirada")
        parar.wait(CORRELATION_INTERVAL_SECONDS)
