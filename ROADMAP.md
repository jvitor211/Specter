# SPECTER — Roadmap de Construção com IA
### Sequência completa de prompts para ir do zero ao MVP funcional

> **Como usar este documento:** Execute cada prompt em ordem. Cole no Claude ou GPT-4.
> Cada bloco é autocontido — o LLM vai gerar o código completo do componente.
> Você revisa, testa, e passa para o próximo.

---

## FASE 1 — INFRAESTRUTURA BASE (Dias 1–7)

### ETAPA 1.1 — Setup do ambiente e banco de dados

```
Crie um arquivo docker-compose.yml para o projeto Specter com os seguintes serviços:

1. PostgreSQL 15 com banco de dados "specter_db"
2. Redis 7 (usado para cache e fila de tarefas Celery)
3. Adminer (interface web para visualizar o banco)

Crie também um arquivo init.sql com o schema completo:

Tabelas necessárias:
- packages: id, name, ecosystem (npm/pypi), created_at, updated_at
- package_versions: id, package_id, version, published_at, maintainer_count, has_postinstall, description, metadata (jsonb)
- package_features: id, package_id, version_id, age_days, typosquatting_score, github_stars, has_github, install_script_risk, maintainer_count, days_since_last_publish, total_versions, risk_score, computed_at
- known_malicious: id, package_id, source (osv/socket/manual), confirmed_at, notes
- scan_requests: id, session_id, package_name, ecosystem, version, risk_score, flagged, created_at

Inclua índices para: packages(name, ecosystem), package_features(risk_score), scan_requests(session_id).

Use variáveis de ambiente com arquivo .env.example.
```

---

### ETAPA 1.2 — Pipeline de ingestão npm

```
Crie um worker Python chamado ingest_npm.py usando Celery + Redis para ingestar o npm registry de forma incremental.

Requisitos:
1. Use a npm registry API pública:
   - Endpoint de todos pacotes: https://replicate.npmjs.com/_all_docs?limit=1000&startkey="LAST_KEY"
   - Endpoint de detalhes: https://registry.npmjs.org/{package_name}
   
2. Implemente ingestão incremental:
   - Salve o último "startkey" processado no Redis para retomar de onde parou
   - Processe em batches de 100 pacotes por vez
   
3. Para cada pacote, extraia e salve no PostgreSQL:
   - nome, versão mais recente, data de publicação, lista de maintainers
   - Se tem scripts.postinstall ou scripts.preinstall
   - URL do repositório (se houver)
   - Número total de versões publicadas
   
4. Rate limiting: máximo 80 requisições por minuto
5. Retry automático com backoff exponencial (3 tentativas)
6. Log de progresso a cada 500 pacotes processados
7. Use SQLAlchemy para o ORM com os models do schema anterior

Use as bibliotecas: celery, redis, httpx, sqlalchemy, tenacity, loguru
```

---

### ETAPA 1.3 — Pipeline de ingestão PyPI

```
Crie um worker Python chamado ingest_pypi.py similar ao npm, mas para o PyPI.

API pública PyPI:
- Lista de todos pacotes: https://pypi.org/simple/ (retorna HTML, parse com BeautifulSoup)
- Detalhes de pacote: https://pypi.org/pypi/{package_name}/json

Para cada pacote, extraia:
- nome, versão mais recente, data de upload
- autor e maintainers (author, maintainer fields)
- requires_dist (dependências)
- project_urls (se tem GitHub)
- classifiers (para detectar pacotes de desenvolvimento vs produção)
- Se tem scripts de entrada (entry_points)

Mesma estrutura de rate limiting e retry do ingest_npm.py.
Use o mesmo modelo SQLAlchemy.

Adicione uma task Celery scheduled para rodar ambos os workers a cada 6 horas.
```

---

### ETAPA 1.4 — Ingestão de dados de ameaças conhecidas (OSV Database)

```
Crie um script Python chamado ingest_osv.py para baixar e processar o OSV Database (Google's Open Source Vulnerability database).

1. Download bulk: https://osv-vulnerabilities.storage.googleapis.com/all.zip
   - Baixe apenas se o arquivo mudou (use ETag/Last-Modified header)
   - Descompacte e processe os JSONs

2. Para cada vulnerabilidade no OSV:
   - Filtre apenas ecosystem "npm" e "PyPI"
   - Extraia: package_name, ecosystem, affected_versions, severity
   - Insira na tabela known_malicious com source = 'osv'

3. Também faça fetch do Socket.dev public feed:
   - https://socket.dev/api/npm/package-score (documentação pública)
   - Salve pacotes com score < 30 como known_malicious com source = 'socket'

4. Adicione deduplicação: não insira duplicatas
5. Rode este script uma vez por dia via Celery beat

Esta tabela será o ground truth para treinar o modelo de ML.
```

---

## FASE 2 — FEATURE ENGINEERING (Dias 7–14)

### ETAPA 2.1 — Extrator de features

```
Crie um módulo Python chamado feature_extractor.py que recebe os dados de um pacote do banco de dados e retorna um dicionário com as seguintes features para uso em ML:

INPUT: Um registro da tabela package_versions (como dict)
OUTPUT: Dict com todas as features abaixo

FEATURES TEMPORAIS:
- package_age_days: dias desde a primeira publicação
- days_since_last_publish: dias desde a última versão
- total_versions: número total de versões publicadas
- version_frequency: total_versions / package_age_days (versões por dia)
- is_new_package: 1 se age < 30 dias, else 0

FEATURES SOCIAIS:
- maintainer_count: número de maintainers
- single_maintainer: 1 se maintainer_count == 1, else 0
- has_github: 1 se tem URL do GitHub, else 0
- github_stars: estrelas no GitHub (faça fetch via GitHub API se has_github=1)
- github_age_days: idade do repo GitHub em dias
- github_contributors: número de contribuidores únicos

FEATURES DE RISCO COMPORTAMENTAL:
- has_postinstall_script: 1 se tem scripts.postinstall, else 0
- has_preinstall_script: 1 se tem scripts.preinstall, else 0
- install_script_length: tamanho em caracteres do install script (0 se não tem)

FEATURES DE TYPOSQUATTING:
- Carregue os top-500 pacotes mais baixados do npm/PyPI (hardcoded ou de arquivo)
- typosquatting_score: maior similaridade de Levenshtein normalizada entre o nome do pacote e qualquer nome nos top-500
- edit_distance_min: menor edit distance absoluta para o top-500
- is_likely_typosquat: 1 se typosquatting_score > 0.85 AND package_age_days < 90

Use as bibliotecas: rapidfuzz (para Levenshtein eficiente), httpx, sqlalchemy
Inclua cache Redis para resultados de GitHub API (TTL de 1 hora)
```

---

### ETAPA 2.2 — Pipeline de computação de features em batch

```
Crie um worker Celery chamado compute_features.py que:

1. Busca todos os pacotes no banco que não têm features computadas (ou foram atualizados após a última computação)
2. Para cada pacote, chama o feature_extractor do passo anterior
3. Salva o resultado na tabela package_features
4. Marca o pacote como processado

Adicione:
- Processamento em paralelo com Celery group (workers concorrentes)
- Limite de 4 workers simultâneos para não sobrecarregar a GitHub API
- Log de progresso
- Task agendada para rodar a cada 2 horas

Também crie uma função compute_single(package_name, ecosystem) que computa features de um pacote específico on-demand (será usada pela API de scan em tempo real).
```

---

## FASE 3 — MODELO DE ML (Dias 14–21)

### ETAPA 3.1 — Preparação do dataset de treino

```
Crie um script Python chamado prepare_training_data.py que:

1. Busca do banco de dados:
   - Todos os pacotes em package_features que têm features computadas
   - Join com known_malicious para criar o label (1 = malicioso, 0 = legítimo)

2. Estratégia de labels:
   - Label 1 (malicioso): pacotes que aparecem em known_malicious
   - Label 0 (legítimo): pacotes com age > 180 dias, github_stars > 100, maintainer_count > 1
   - Ignore pacotes sem classificação clara (zona cinza)

3. Lide com class imbalance:
   - Maliciosos são minoria — use SMOTE ou class_weight='balanced'
   - Reporte a distribuição de classes

4. Output:
   - Salve X_train, X_test, y_train, y_test como arquivos .parquet
   - Salve a lista de feature names em features.json
   - Salve estatísticas do dataset em dataset_stats.json

5. Faça análise exploratória básica:
   - Correlação entre features e label
   - Distribuição de cada feature por classe
   - Salve um relatório em dataset_report.txt

Use: pandas, scikit-learn, imbalanced-learn, pyarrow
```

---

### ETAPA 3.2 — Treinamento do modelo Wings

```
Crie um script Python chamado train_model.py para treinar o modelo Wings do Specter.

1. Carregue os dados de prepare_training_data.py

2. Treine 3 modelos e compare:
   - XGBoostClassifier (modelo principal)
   - RandomForestClassifier (ensemble secundário)
   - LogisticRegression (baseline)

3. Para XGBoost, faça hyperparameter tuning com Optuna:
   - n_estimators: [100, 500]
   - max_depth: [3, 8]
   - learning_rate: [0.01, 0.3]
   - scale_pos_weight (para class imbalance)
   - 20 trials, optimize F1-score

4. Métricas obrigatórias:
   - Precision, Recall, F1 (foco em Recall alto — falso negativo é pior que falso positivo)
   - ROC-AUC
   - Confusion matrix
   - Feature importance ranking

5. Salve:
   - Modelo treinado: models/wings_v1.joblib
   - Threshold ótimo (maximize F1): models/threshold.json
   - Relatório completo: models/training_report.txt
   - Feature importance: models/feature_importance.json

6. Crie uma função predict(features_dict) -> {"score": float, "top_reasons": list}
   que retorna o score e as 3 features que mais contribuíram para o risco

Use: xgboost, scikit-learn, optuna, joblib, shap (para feature importance)
```

---

### ETAPA 3.3 — Camada LLM para análise semântica

```
Crie um módulo Python chamado llm_analyzer.py para análise semântica de pacotes borderline.

Este módulo é chamado quando o score do Wings está entre 0.3 e 0.7 (zona de incerteza).

Função principal: analyze_package(package_data: dict) -> dict

1. Monte um prompt estruturado com:
   - Nome do pacote e ecossistema
   - Descrição do README (primeiros 500 chars)
   - Conteúdo do install script (se existir)
   - Lista de dependências
   - Metadata: idade, maintainers, github_url

2. Prompt para o LLM:
   "Você é um especialista em segurança de supply chain de software. 
   Analise este pacote e responda APENAS em JSON com:
   {
     'is_suspicious': bool,
     'confidence': float (0-1),
     'reasons': [string, ...] (máximo 3),
     'verdict': 'safe' | 'suspicious' | 'malicious'
   }
   Sinais de risco: nomes similares a pacotes populares, install scripts com acesso à rede,
   leitura de variáveis de ambiente sensíveis, acesso a ~/.ssh ou ~/.aws."

3. Use a Anthropic API (claude-sonnet-4-6) ou OpenAI API (gpt-4o-mini)
   - Configure via variável de ambiente SPECTER_LLM_PROVIDER
   - Custo estimado: ~$0.002 por análise

4. Cache os resultados no Redis por 24 horas (evitar re-análise do mesmo pacote)

5. Retorne um score combinado: 0.7 * wings_score + 0.3 * llm_confidence

Use: anthropic (ou openai), redis, pydantic para validação do JSON de resposta
```

---

## FASE 4 — API REST (Dias 21–28)

### ETAPA 4.1 — API principal com FastAPI

```
Crie uma API REST completa em Python com FastAPI para o Specter.

Arquivo: api/main.py

ENDPOINTS:

POST /v1/scan
- Body: {"packages": [{"name": "lodash", "version": "4.17.21", "ecosystem": "npm"}]}
- Máximo 50 pacotes por request
- Para cada pacote:
  1. Busca no cache Redis (TTL 1 hora)
  2. Se não tem cache: busca features do banco, roda Wings model, salva score
  3. Se score entre 0.3-0.7: chama llm_analyzer
  4. Retorna: score, verdict (safe/review/blocked), top_reasons, recommendation
- Response time target: < 200ms (com cache), < 2s (sem cache)

GET /v1/package/{ecosystem}/{name}
- Retorna histórico completo de risco de um pacote
- Inclui: todas as versões, evolução do score, motivos históricos

GET /v1/health
- Status da API, versão do modelo, última atualização do banco

POST /v1/feedback
- Permite clientes reportar falsos positivos/negativos
- Body: {"package": str, "ecosystem": str, "version": str, "is_false_positive": bool}
- Salva no banco para retreino futuro

MIDDLEWARE:
- Rate limiting: 100 req/min por API key (free), ilimitado (pro)
- API key via header X-Specter-Key
- CORS configurado para *.specter.dev
- Request logging com tempo de resposta

AUTENTICAÇÃO SIMPLES:
- Tabela api_keys no banco: id, key_hash, tier (free/pro/enterprise), requests_today
- Middleware verifica key e incrementa contador

Use: fastapi, uvicorn, redis, sqlalchemy, pydantic
```

---

### ETAPA 4.2 — Sistema de API Keys e billing básico

```
Crie um módulo api/auth.py com sistema simples de API keys para o Specter.

1. Modelo de dados (adicione ao schema SQL):
   - api_keys: id, key_hash (sha256), email, tier, requests_this_month, created_at, last_used_at
   - usage_logs: id, api_key_id, endpoint, timestamp, response_time_ms, packages_scanned

2. Funções necessárias:
   - generate_key() -> str: gera key aleatória formato "spk_live_XXXXXXXXXXXXXXXX"
   - hash_key(key) -> str: hash SHA256 para armazenar com segurança
   - validate_key(key) -> APIKey | None: valida e retorna dados da key
   - check_rate_limit(key_id, tier) -> bool: verifica se não excedeu limite mensal
   - log_usage(key_id, endpoint, response_time, packages_count)

3. Limites por tier:
   - free: 500 scans/mês
   - pro: ilimitado
   - enterprise: ilimitado + endpoints extras

4. Endpoint de gerenciamento:
   POST /v1/keys/create (sem auth): cria nova key free com email
   GET /v1/keys/usage (com auth): retorna uso do mês atual

Use: fastapi, sqlalchemy, hashlib, secrets
```

---

## FASE 5 — PLUGIN VS CODE (Dias 28–40)

### ETAPA 5.1 — Estrutura base do plugin

```
Crie a estrutura completa de um plugin VS Code em TypeScript chamado "specter-security".

Arquivos necessários:
- package.json (manifest do plugin)
- src/extension.ts (entry point)
- src/scanner.ts (lógica de scan)
- src/diagnostics.ts (highlights no editor)
- src/statusBar.ts (status bar item)
- tsconfig.json
- .vscodeignore

FUNCIONALIDADES:

1. Ativação automática ao abrir arquivos:
   - package.json (projetos npm)
   - requirements.txt, pyproject.toml (projetos Python)
   - Qualquer arquivo .ts, .js, .py com imports

2. Scan de imports em tempo real:
   - Detecta imports/requires no arquivo atual
   - Extrai nome do pacote e versão
   - Chama a Specter API (https://api.specter.dev/v1/scan)
   - Debounce de 1 segundo para não spammar a API

3. Diagnósticos visuais:
   - Score > 0.7: linha vermelha de erro com mensagem "⚠ Specter: High risk package"
   - Score 0.3-0.7: linha amarela de warning "⚡ Specter: Review recommended"
   - Score < 0.3: sem indicação (clean)
   - Hover tooltip mostra: score, top 3 reasons, link para relatório completo

4. Status bar:
   - Mostra "Specter: Scanning..." durante scan
   - Mostra "Specter: ✓ 12 clean" ou "Specter: ⚠ 2 flagged" após scan
   - Click abre relatório no browser

5. Comando: "Specter: Scan All Dependencies"
   - Lê todo package.json ou requirements.txt
   - Scanneia todos os pacotes de uma vez
   - Mostra resultado em output panel

6. Configurações (settings.json):
   - specter.apiKey: string (API key do usuário)
   - specter.riskThreshold: number (default 0.5)
   - specter.autoScan: boolean (default true)

Use apenas a VS Code Extension API oficial. Sem dependências externas além do vscode.
```

---

### ETAPA 5.2 — GitHub Action

```
Crie um GitHub Action completo chamado "specter-scan" para bloquear PRs com dependências de risco.

Arquivos:
- action.yml (manifest do action)
- src/index.ts (lógica principal)
- Dockerfile (para container action)

FUNCIONAMENTO:
1. Triggered em: pull_request (opened, synchronize)
2. Lê package.json e/ou requirements.txt do repositório
3. Chama Specter API com todos os pacotes
4. Se algum pacote tem score > threshold:
   - Falha o check (exit code 1)
   - Posta comment no PR com lista dos pacotes flagged e motivos
   - Comment formatado em markdown com tabela

INPUTS (action.yml):
- api_key: required (Specter API key)
- risk_threshold: optional, default '0.5'
- ecosystems: optional, default 'npm,pypi'
- fail_on_review: optional (se deve falhar também em warnings), default 'false'
- comment_on_pr: optional, default 'true'

OUTPUTS:
- packages_scanned: número de pacotes verificados
- packages_flagged: número de pacotes flagged
- report_url: URL do relatório completo

Exemplo de uso no workflow:
- uses: specter-security/scan-action@v1
  with:
    api_key: ${{ secrets.SPECTER_API_KEY }}
    risk_threshold: '0.6'

Use: @actions/core, @actions/github, node-fetch
```

---

## FASE 6 — DASHBOARD WEB (Dias 40–50)

### ETAPA 6.1 — Dashboard de monitoramento

```
Crie um dashboard web em Next.js 14 com App Router para o Specter.

Páginas necessárias:

1. /dashboard — visão geral
   - Total de scans do mês
   - Pacotes flagged vs clean (donut chart com Recharts)
   - Últimos 10 scans (tabela com status)
   - Scans por dia (line chart últimos 30 dias)

2. /packages — explorador de pacotes
   - Busca por nome de pacote
   - Mostra: score de risco, histórico de versões, reasons
   - Filtros: ecosystem, risk level, date range

3. /settings — configurações
   - Mostrar/copiar API key
   - Uso do mês (progress bar vs limite do tier)
   - Upgrade de tier

DESIGN:
- Dark theme (fundo #080910, igual à landing page)
- Fonte Syne para títulos, Space Mono para dados
- Cor de risco: vermelho (#ff2d4a) para blocked, amarelo para review, verde para safe
- Sidebar fixa com navegação
- Totalmente responsivo

AUTENTICAÇÃO:
- Simples: login com API key (campo de texto)
- Salva no localStorage
- Todas as chamadas de API incluem X-Specter-Key header

Use: next.js 14, recharts, tailwindcss, shadcn/ui
```

---

## FASE 7 — LANÇAMENTO (Dias 50–60)

### ETAPA 7.1 — Script de análise para o relatório técnico

```
Crie um script Python chamado generate_threat_report.py que analisa o banco de dados do Specter e gera um relatório técnico para publicação.

O relatório deve encontrar e documentar:

1. TOP 10 pacotes suspeitos detectados:
   - Nome, ecosystem, score, principais reasons
   - Data de publicação, número de downloads estimado
   - Comparação com o pacote legítimo que estão imitando

2. Estatísticas gerais:
   - Total de pacotes analisados
   - % com score > 0.7 (high risk)
   - % com score 0.3-0.7 (review)
   - Distribuição por ecosystem

3. Padrões encontrados:
   - Tipos de typosquatting mais comuns
   - Características mais frequentes em pacotes maliciosos
   - Timeline: quando foram publicados vs quando foram detectados

4. Comparação com ferramentas existentes:
   - Quantos desses pacotes estão no OSV (já conhecidos)
   - Quantos são NOVOS (detectados apenas pelo Specter)
   - Este número é o seu "exclusive detections" — é o KPI principal do relatório

OUTPUT:
- threat_report.md: relatório formatado em markdown pronto para publicar
- threat_report_data.json: dados brutos para jornalistas/pesquisadores

Este relatório é o seu "exploit demo" — o conteúdo que você publica no Hacker News
e LinkedIn para gerar awareness e inbound de clientes.
```

---

## CHECKLIST DE PROGRESSO

| Fase | Etapa | Status | Dia alvo |
|------|-------|--------|----------|
| 1 | 1.1 Docker + Schema SQL | ⬜ | Dia 1 |
| 1 | 1.2 Ingestão npm | ⬜ | Dia 2 |
| 1 | 1.3 Ingestão PyPI | ⬜ | Dia 3 |
| 1 | 1.4 Ingestão OSV + Socket | ⬜ | Dia 4 |
| 2 | 2.1 Feature extractor | ⬜ | Dia 8 |
| 2 | 2.2 Compute features batch | ⬜ | Dia 10 |
| 3 | 3.1 Preparação dataset | ⬜ | Dia 15 |
| 3 | 3.2 Treinamento Wings | ⬜ | Dia 17 |
| 3 | 3.3 Camada LLM | ⬜ | Dia 19 |
| 4 | 4.1 API FastAPI | ⬜ | Dia 23 |
| 4 | 4.2 Auth + API Keys | ⬜ | Dia 25 |
| 5 | 5.1 Plugin VS Code | ⬜ | Dia 32 |
| 5 | 5.2 GitHub Action | ⬜ | Dia 36 |
| 6 | 6.1 Dashboard Next.js | ⬜ | Dia 45 |
| 7 | 7.1 Relatório técnico | ⬜ | Dia 55 |
| 7 | **LANÇAMENTO PÚBLICO** | ⬜ | **Dia 60** |

---

## DICAS PARA USAR OS PROMPTS COM EFICIÊNCIA

**Antes de cada prompt:**
- Cole o schema SQL da Etapa 1.1 como contexto
- Diga qual etapa anterior já foi concluída

**Quando o código gerado tiver erro:**
- Cole o stack trace completo e diga: *"Este erro aconteceu ao rodar o código acima, corrija"*

**Para integrar componentes:**
- Diga: *"Integre o [componente X] com o [componente Y] gerado anteriormente, respeitando as interfaces definidas"*

**Para testes:**
- Após cada etapa: *"Crie um script de teste simples para validar que [componente] está funcionando corretamente com dados mock"*

---

*Specter — See what others can't.*