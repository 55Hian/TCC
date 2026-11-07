CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS usuario (
    id_morador SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    status_ativo BOOLEAN DEFAULT TRUE,
    vetor_facial vector(128)
);

CREATE TABLE IF NOT EXISTS sessoes_tracking (
    id_sessao SERIAL PRIMARY KEY,
    id_morador INTEGER REFERENCES usuario(id_morador),
    track_id INTEGER NOT NULL,
    entrada TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    saida TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sessoes_compra (
    id_sessao SERIAL PRIMARY KEY,
    id_morador INTEGER NOT NULL REFERENCES usuario(id_morador),
    inicio_sessao TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fim_sessao TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'EM_ANDAMENTO',
    track_id_atual INTEGER
);

CREATE TABLE IF NOT EXISTS produto (
    id_produto SERIAL PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    classe_modelo VARCHAR(100) NOT NULL UNIQUE,
    peso DOUBLE PRECISION NOT NULL CHECK (peso > 0),
    descricao TEXT NOT NULL DEFAULT '',
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE produto ADD COLUMN IF NOT EXISTS peso DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS evento (
    id_event SERIAL PRIMARY KEY,
    tipo VARCHAR(100) NOT NULL,
    produto VARCHAR(100) NOT NULL,
    quantidade INTEGER NOT NULL DEFAULT 1,
    mao_id INTEGER,
    produto_id INTEGER,
    pontos_mao VARCHAR(100),
    metodo VARCHAR(100),
    interpretacao VARCHAR(100),
    data_inc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    video_path TEXT,
    video_status VARCHAR(24) NOT NULL DEFAULT 'nao_solicitado'
);

ALTER TABLE evento ADD COLUMN IF NOT EXISTS video_path TEXT;
ALTER TABLE evento ADD COLUMN IF NOT EXISTS video_status VARCHAR(24) NOT NULL DEFAULT 'nao_solicitado';

CREATE INDEX IF NOT EXISTS idx_evento_data_inc ON evento (data_inc DESC);

CREATE TABLE IF NOT EXISTS variacao_balanca (
    id_variacao BIGSERIAL PRIMARY KEY,
    variacao_peso DOUBLE PRECISION NOT NULL,
    momento TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_variacao_balanca_momento ON variacao_balanca (momento DESC);
CREATE INDEX IF NOT EXISTS idx_variacao_retirada_momento
    ON variacao_balanca (momento, id_variacao) WHERE variacao_peso < 0;
CREATE INDEX IF NOT EXISTS idx_evento_interacao_data
    ON evento (data_inc, id_event) WHERE tipo = 'interacao_mao';

CREATE TABLE IF NOT EXISTS correlacao_retirada (
    id_retirada BIGSERIAL PRIMARY KEY,
    id_event INTEGER NOT NULL REFERENCES evento(id_event),
    id_variacao BIGINT NOT NULL REFERENCES variacao_balanca(id_variacao),
    id_produto INTEGER,
    nome_produto VARCHAR(120),
    peso_produto DOUBLE PRECISION,
    timestamp_camera TIMESTAMPTZ,
    timestamp_balanca TIMESTAMPTZ,
    video_path TEXT,
    video_status VARCHAR(24) NOT NULL DEFAULT 'nao_solicitado',
    momento_retirada TIMESTAMPTZ NOT NULL,
    estado VARCHAR(24) NOT NULL DEFAULT 'confirmada',
    criada_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_event, id_variacao)
);

CREATE INDEX IF NOT EXISTS idx_correlacao_retirada_variacao
    ON correlacao_retirada (id_variacao);
CREATE INDEX IF NOT EXISTS idx_correlacao_retirada_criada
    ON correlacao_retirada (criada_em DESC);

ALTER TABLE correlacao_retirada ADD COLUMN IF NOT EXISTS id_produto INTEGER;
ALTER TABLE correlacao_retirada ADD COLUMN IF NOT EXISTS nome_produto VARCHAR(120);
ALTER TABLE correlacao_retirada ADD COLUMN IF NOT EXISTS peso_produto DOUBLE PRECISION;
ALTER TABLE correlacao_retirada ADD COLUMN IF NOT EXISTS timestamp_camera TIMESTAMPTZ;
ALTER TABLE correlacao_retirada ADD COLUMN IF NOT EXISTS timestamp_balanca TIMESTAMPTZ;
ALTER TABLE correlacao_retirada ADD COLUMN IF NOT EXISTS video_path TEXT;
ALTER TABLE correlacao_retirada ADD COLUMN IF NOT EXISTS video_status VARCHAR(24) NOT NULL DEFAULT 'nao_solicitado';

UPDATE correlacao_retirada c
SET id_produto = e.produto_id,
    nome_produto = COALESCE(p.nome, e.produto),
    peso_produto = p.peso,
    timestamp_camera = e.data_inc AT TIME ZONE 'UTC',
    timestamp_balanca = v.momento AT TIME ZONE 'UTC',
    video_path = e.video_path,
    video_status = e.video_status
FROM evento e CROSS JOIN variacao_balanca v
LEFT JOIN produto p ON p.id_produto = e.produto_id
WHERE e.id_event = c.id_event
  AND v.id_variacao = c.id_variacao
  AND (c.timestamp_camera IS NULL OR c.timestamp_balanca IS NULL
       OR c.video_status = 'nao_solicitado');




