-- =============================================================================
-- SPECTER — Schema Inicial do Banco de Dados
-- Todas as tabelas necessarias para o MVP (Fases 1-4)
-- =============================================================================

-- Extensao para gerar UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- 1. pacotes — registro principal de cada pacote (npm/pypi)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pacotes (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(255) NOT NULL,
    ecossistema     VARCHAR(20)  NOT NULL DEFAULT 'npm',  -- 'npm' | 'pypi'
    descricao       TEXT,
    url_repositorio VARCHAR(512),
    criado_em       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_pacotes_nome_eco UNIQUE (nome, ecossistema)
);

CREATE INDEX IF NOT EXISTS ix_pacotes_nome ON pacotes (nome);
CREATE INDEX IF NOT EXISTS ix_pacotes_ecossistema ON pacotes (ecossistema);

-- ---------------------------------------------------------------------------
-- 2. versoes_pacote — cada versao publicada de um pacote
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS versoes_pacote (
    id                    SERIAL PRIMARY KEY,
    pacote_id             INTEGER      NOT NULL REFERENCES pacotes(id) ON DELETE CASCADE,
    versao                VARCHAR(100) NOT NULL,
    publicado_em          TIMESTAMPTZ,
    contagem_mantenedores INTEGER      DEFAULT 0,
    tem_postinstall       BOOLEAN      DEFAULT FALSE,
    tem_preinstall        BOOLEAN      DEFAULT FALSE,
    descricao             TEXT,
    scripts               JSONB        DEFAULT '{}'::jsonb,
    dependencias          JSONB        DEFAULT '{}'::jsonb,
    mantenedores          JSONB        DEFAULT '[]'::jsonb,
    metadados             JSONB        DEFAULT '{}'::jsonb,
    criado_em             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_versao_pacote UNIQUE (pacote_id, versao)
);

CREATE INDEX IF NOT EXISTS ix_versoes_pacote_id ON versoes_pacote (pacote_id);

-- ---------------------------------------------------------------------------
-- 3. features_pacote — features computadas para ML
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS features_pacote (
    id                          SERIAL PRIMARY KEY,
    pacote_id                   INTEGER NOT NULL REFERENCES pacotes(id) ON DELETE CASCADE,
    versao_id                   INTEGER REFERENCES versoes_pacote(id) ON DELETE SET NULL,

    -- Temporais
    idade_dias                  INTEGER,
    dias_desde_ultima_publicacao INTEGER,
    total_versoes               INTEGER,
    frequencia_versoes          FLOAT,
    pacote_novo                 BOOLEAN DEFAULT FALSE,

    -- Sociais
    contagem_mantenedores       INTEGER,
    mantenedor_unico            BOOLEAN DEFAULT FALSE,
    tem_github                  BOOLEAN DEFAULT FALSE,
    estrelas_github             INTEGER,
    idade_github_dias           INTEGER,
    contribuidores_github       INTEGER,

    -- Risco comportamental
    tem_script_postinstall      BOOLEAN DEFAULT FALSE,
    tem_script_preinstall       BOOLEAN DEFAULT FALSE,
    tamanho_script_instalacao   INTEGER DEFAULT 0,

    -- Typosquatting
    score_typosquatting         FLOAT,
    distancia_edicao_minima     INTEGER,
    provavel_typosquat          BOOLEAN DEFAULT FALSE,

    -- Score final
    score_risco                 FLOAT,
    computado_em                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_features_pacote_id ON features_pacote (pacote_id);
CREATE INDEX IF NOT EXISTS ix_features_score_risco ON features_pacote (score_risco);

-- ---------------------------------------------------------------------------
-- 4. maliciosos_conhecidos — ground truth para treino do modelo
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS maliciosos_conhecidos (
    id          SERIAL PRIMARY KEY,
    pacote_id   INTEGER      NOT NULL REFERENCES pacotes(id) ON DELETE CASCADE,
    fonte       VARCHAR(50)  NOT NULL DEFAULT 'manual',  -- 'osv' | 'socket' | 'manual'
    confirmado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notas       TEXT,

    CONSTRAINT uq_malicioso_pacote_fonte UNIQUE (pacote_id, fonte)
);

CREATE INDEX IF NOT EXISTS ix_maliciosos_pacote ON maliciosos_conhecidos (pacote_id);

-- ---------------------------------------------------------------------------
-- 5. requisicoes_scan — log de scans feitos via API
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS requisicoes_scan (
    id            SERIAL PRIMARY KEY,
    id_sessao     UUID         DEFAULT uuid_generate_v4(),
    nome_pacote   VARCHAR(255) NOT NULL,
    ecossistema   VARCHAR(20)  NOT NULL DEFAULT 'npm',
    versao        VARCHAR(100),
    score_risco   FLOAT,
    sinalizado    BOOLEAN      DEFAULT FALSE,
    criado_em     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_scan_sessao ON requisicoes_scan (id_sessao);

-- ---------------------------------------------------------------------------
-- 6. chaves_api — autenticacao e billing
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chaves_api (
    id                  SERIAL PRIMARY KEY,
    hash_chave          VARCHAR(64)  NOT NULL UNIQUE,
    email               VARCHAR(255) NOT NULL,
    tier                VARCHAR(20)  NOT NULL DEFAULT 'free',  -- 'free' | 'pro' | 'enterprise'
    requisicoes_mes     INTEGER      DEFAULT 0,
    criado_em           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ultimo_uso_em       TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- 7. logs_uso — metricas de uso da API
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs_uso (
    id                  SERIAL PRIMARY KEY,
    chave_api_id        INTEGER      NOT NULL REFERENCES chaves_api(id) ON DELETE CASCADE,
    endpoint            VARCHAR(255) NOT NULL,
    timestamp_req       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    tempo_resposta_ms   INTEGER,
    pacotes_escaneados  INTEGER      DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- 8. registro_etag — cache de ETags para download incremental
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS registro_etag (
    id            SERIAL PRIMARY KEY,
    endpoint      VARCHAR(512) NOT NULL UNIQUE,
    etag          VARCHAR(512),
    ultimo_cursor VARCHAR(512),
    atualizado_em TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
