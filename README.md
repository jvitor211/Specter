<p align="center">
  <img src="assets/icon.svg" width="80" alt="Specter Logo" />
</p>

<h1 align="center">Specter</h1>

<p align="center">
  <strong>See what others can't.</strong><br>
  AI-powered detection of malicious and typosquatted packages in npm and PyPI supply chains.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License MIT"></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/next.js-14-black.svg" alt="Next.js 14">
  <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status Alpha">
</p>

---

## The Problem

LLMs hallucinate package names. Attackers register them. A single `pip install` or `npm install` of a poisoned dependency can exfiltrate secrets, install backdoors, or compromise your entire CI pipeline.

Traditional security scanners only flag known CVEs. They miss the zero-day window — new packages with no history, no stars, and a name that's one typo away from `requests` or `lodash`.

**Specter closes that gap.** It continuously ingests npm and PyPI, runs 40+ risk signals on every package, scores them with an XGBoost ML model, and blocks threats before they reach your code — in your IDE, your CI, your API.

## Quick Demo

```
$ specter scan --threshold 0.5

→ Indexing 47 dependencies...
→ Running Wings ML engine...
→ Checking 3,100,000 package signatures...

✓ lodash@4.17.21        score: 0.02  [SAFE]
✓ react@18.2.0          score: 0.01  [SAFE]
✓ axios@1.6.0           score: 0.03  [SAFE]
⚠ crypo@1.0.0           score: 0.71  [REVIEW]
  └ typosquatting: 0.94 (→ crypto)
  └ published: 3 days ago, 0 stars
✗ reqeusts@2.28.0       score: 0.94  [BLOCKED]
  └ typosquatting: 0.97 (→ requests)
  └ postinstall: network egress detected
  └ LLM analysis: likely malicious

✗ 1 blocked / ⚠ 1 flagged / ✓ 45 clean
```

## Installation

### VS Code Plugin

Install from `.vsix` or the Marketplace:

```bash
code --install-extension specter-security-0.1.0.vsix
```

Configure in VS Code settings:
- `specter.apiUrl` — API endpoint (default: `http://localhost:8000`)
- `specter.apiKey` — Your API key (`spk_live_...`)
- `specter.riskThreshold` — Score threshold for flagging (default: `0.5`)

### GitHub Action

```yaml
- uses: specter-security/specter-scan@v1
  with:
    api-key: ${{ secrets.SPECTER_API_KEY }}
    threshold: 0.5
    fail-on-block: true
```

### REST API

```bash
curl -X POST http://localhost:8000/v1/scan \
  -H "Content-Type: application/json" \
  -H "X-Specter-Key: spk_live_..." \
  -d '{"packages": [{"name": "lodash", "ecosystem": "npm"}]}'
```

### Self-Hosted (Docker)

```bash
git clone https://github.com/specter-security/specter.git
cd specter
cp .env.example .env          # Edit with your keys
docker-compose up -d           # PostgreSQL + Redis + Adminer
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
alembic upgrade head
uvicorn specter.api.main:app --host 0.0.0.0 --port 8000
```

## How It Works

```
  ┌─────────────┐    ┌──────────────┐    ┌────────────┐    ┌───────────┐
  │  npm / PyPI  │───>│  Ingestion   │───>│  Feature   │───>│   Wings   │
  │  Registries  │    │  (Celery)    │    │ Extraction │    │ ML Model  │
  └─────────────┘    └──────────────┘    └────────────┘    └─────┬─────┘
                                                                 │
         ┌──────────────────────────────────────────────────────┘
         │
         v
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │  Score 0-1   │───>│  LLM Deep    │───>│   Block /    │
  │  Per Package │    │  Analysis    │    │   Allow      │
  └──────────────┘    │ (Borderline) │    └──────┬───────┘
                      └──────────────┘           │
                                    ┌────────────┼────────────┐
                                    │            │            │
                                    v            v            v
                              ┌──────────┐ ┌──────────┐ ┌──────────┐
                              │ VS Code  │ │ GitHub   │ │   REST   │
                              │ Plugin   │ │ Action   │ │   API    │
                              └──────────┘ └──────────┘ └──────────┘
```

### Risk Signals (40+)

| Signal | Description |
|--------|-------------|
| `typosquatting_score` | Levenshtein distance to top-500 packages |
| `package_age_days` | Days since first publish |
| `has_postinstall` | Suspicious lifecycle scripts |
| `num_maintainers` | Single-maintainer risk |
| `github_stars` | Repository credibility |
| `description_length` | Empty or suspiciously short descriptions |
| `days_since_last_publish` | Dormant or just-created packages |
| `known_malicious` | Match against OSV, Socket.dev feeds |
| ... | 30+ additional features |

## Architecture

```
specter/
├── api/              # FastAPI REST endpoints
│   ├── auth.py       # API key auth + tier rate limiting
│   └── rotas/        # scan, packages, feedback, keys, stats
├── ingestao/         # Celery workers: npm, PyPI, OSV ingestion
├── features/         # Feature extraction (GitHub, typosquatting)
├── ml/               # XGBoost training, LLM analysis, SHAP
├── modelos/          # SQLAlchemy ORM models
└── utils/            # Structured logging (structlog + JSON)

dashboard/            # Next.js 14 web dashboard (dark theme)
vscode-plugin/        # VS Code extension (TypeScript)
github-action/        # GitHub Action (composite)
tests/                # pytest test suite
migrations/           # Alembic database migrations
```

### Stack

| Layer | Technology |
|-------|-----------|
| Database | PostgreSQL 15 |
| Queue / Cache | Redis 7 + Celery |
| Backend API | FastAPI + uvicorn |
| ML Engine | XGBoost + scikit-learn + SHAP |
| LLM Analysis | Claude / GPT (configurable) |
| Frontend | Next.js 14 + Tailwind CSS + Recharts |
| VS Code | Extension API + TypeScript |
| CI/CD | GitHub Actions |

## API Reference

Full interactive docs available at `http://localhost:8000/docs` (Swagger UI).

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/v1/scan` | Key | Scan up to 50 packages |
| `GET` | `/v1/package/{eco}/{name}` | Key | Package risk details |
| `GET` | `/v1/health` | No | API status |
| `POST` | `/v1/keys/create` | No | Create free API key |
| `GET` | `/v1/keys/usage` | Key | Monthly usage stats |
| `POST` | `/v1/keys/upgrade` | Key | Upgrade tier |
| `POST` | `/v1/feedback` | Key | Report false positive |
| `GET` | `/v1/stats` | No | Dashboard statistics |

## Tiers

| | Free | Pro | Enterprise |
|---|---|---|---|
| **Price** | $0 | $49/dev/mo | Custom |
| **Scans** | 500/month | Unlimited | Unlimited |
| **VS Code Plugin** | Yes | Yes | Yes |
| **GitHub Action** | — | Yes | Yes |
| **API Access** | — | Full | Full |
| **LLM Deep Analysis** | — | Yes | Yes |
| **Compliance Reports** | — | — | SOC2, LGPD |
| **On-prem Deploy** | — | — | Yes |

## Roadmap

**Current status**: Alpha (Phase 1-6 complete). Core ingestion, feature extraction, ML scoring, REST API, dashboard, VS Code plugin, and GitHub Action are all functional.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). We welcome bug fixes, new ecosystem support, ML improvements, and documentation.

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md) for responsible disclosure.

## License

[MIT](LICENSE) — Copyright 2026 Specter Security.
