-- Habilita a extensão para cálculos matemáticos de similaridade facial
CREATE EXTENSION IF NOT EXISTS vector;

-- Armazena os moradores autorizados a entrar no micro mercado
CREATE TABLE usuario (
    id_morador SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    status_ativo BOOLEAN DEFAULT TRUE,
    vetor_facial vector(128) -- Array de 128 posições gerado pela IA
);

-- Registra quem está no ambiente para posterior cruzamento com a balança
CREATE TABLE sessoes_tracking (
    id_sessao SERIAL PRIMARY KEY,
    id_morador INT REFERENCES usuario(id_morador),
    track_id INT NOT NULL,
    entrada TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    saida TIMESTAMP
);

CREATE TABLE sessoes_compra (
    id_sessao SERIAL PRIMARY KEY,

    id_morador INTEGER NOT NULL,

    inicio_sessao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    fim_sessao TIMESTAMP,

    status VARCHAR(20) NOT NULL DEFAULT 'EM_ANDAMENTO',

    track_id_atual INTEGER,

    CONSTRAINT fk_sessao_morador
        FOREIGN KEY (id_morador)
        REFERENCES usuario(id_morador)
);

create table evento (
    id_event serial PRIMARY KEY,
    tipo VARCHAR(100),
    produto VARCHAR(100),
    quantidade int,
    mao_id int,
    produto_id int,
    pontos_mao VARCHAR(100),
    metodo VARCHAR(100),
    interpretacao VARCHAR(100),
    data_inc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

