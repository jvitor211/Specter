"""
Gerenciamento da lista dos top-500 pacotes mais baixados (npm/PyPI).
Usada para calcular score de typosquatting via similaridade Levenshtein.

Estrategia:
  - Lista estatica carregada de data/top_500_npm.json (fallback hardcoded)
  - Cache em memoria com TTL de 24h
  - Tarefa Celery para atualizar via api.npmjs.org/downloads/point/last-month
"""

import json
import time
from pathlib import Path

import httpx

from specter.config import config
from specter.utils.logging_config import obter_logger

log = obter_logger("top_pacotes")

_CACHE_TTL = 86400  # 24 horas
_cache: dict = {"pacotes": [], "timestamp": 0.0}

_TOP_500_FALLBACK = [
    "lodash", "chalk", "request", "commander", "express", "react", "debug",
    "async", "bluebird", "moment", "underscore", "fs-extra", "glob", "mkdirp",
    "minimist", "uuid", "semver", "colors", "through2", "yargs", "body-parser",
    "webpack", "babel-core", "typescript", "eslint", "prettier", "jest",
    "mocha", "chai", "sinon", "axios", "node-fetch", "inquirer", "rimraf",
    "cross-env", "dotenv", "concurrently", "nodemon", "pm2", "cors",
    "jsonwebtoken", "bcrypt", "mongoose", "sequelize", "pg", "mysql2",
    "redis", "socket.io", "ws", "cheerio", "puppeteer", "sharp",
    "multer", "passport", "helmet", "compression", "morgan", "winston",
    "pino", "bunyan", "rxjs", "ramda", "immutable", "classnames",
    "prop-types", "react-dom", "react-router", "react-router-dom",
    "redux", "react-redux", "next", "gatsby", "vue", "angular",
    "svelte", "ember-cli", "backbone", "jquery", "bootstrap",
    "tailwindcss", "postcss", "autoprefixer", "sass", "less",
    "styled-components", "emotion", "material-ui", "antd",
    "d3", "chart.js", "three", "pixi.js", "phaser",
    "electron", "nw", "cordova", "react-native", "expo",
    "aws-sdk", "firebase", "stripe", "twilio", "sendgrid",
    "googleapis", "azure-storage", "minio", "got", "superagent",
    "form-data", "formidable", "busboy", "cookie-parser", "express-session",
    "connect-redis", "ioredis", "bull", "agenda", "cron",
    "node-cron", "date-fns", "dayjs", "luxon", "numeral",
    "validator", "joi", "yup", "zod", "ajv",
    "handlebars", "ejs", "pug", "nunjucks", "mustache",
    "marked", "markdown-it", "highlight.js", "prismjs",
    "ora", "cli-progress", "listr", "boxen", "figlet",
    "meow", "yargs-parser", "minimatch", "micromatch", "picomatch",
    "chokidar", "watchman", "graceful-fs", "vinyl", "vinyl-fs",
    "gulp", "grunt", "rollup", "parcel", "esbuild", "vite",
    "swc", "terser", "uglify-js", "clean-css", "cssnano",
    "babel-loader", "ts-loader", "css-loader", "style-loader",
    "file-loader", "url-loader", "html-webpack-plugin",
    "mini-css-extract-plugin", "copy-webpack-plugin",
    "webpack-dev-server", "webpack-merge", "webpack-cli",
    "http-proxy-middleware", "express-http-proxy", "proxy-agent",
    "https-proxy-agent", "socks-proxy-agent", "tunnel",
    "ip", "cidr-regex", "netmask", "dns-packet",
    "crypto-js", "bcryptjs", "argon2", "jose", "jsonwebtoken",
    "passport-jwt", "passport-local", "passport-google-oauth20",
    "passport-github2", "passport-facebook", "oauth",
    "openid-client", "saml2-js", "speakeasy", "otplib",
    "qrcode", "jsqr", "sharp", "jimp", "gm",
    "canvas", "pdfkit", "pdf-lib", "pdf-parse", "xlsx",
    "csv-parse", "csv-stringify", "papaparse", "fast-csv",
    "xml2js", "fast-xml-parser", "cheerio", "jsdom", "htmlparser2",
    "iconv-lite", "encoding", "chardet", "buffer",
    "readable-stream", "pump", "pipeline", "stream-transform",
    "tar", "archiver", "adm-zip", "yauzl", "yazl",
    "lru-cache", "quick-lru", "node-cache", "keyv",
    "leveldown", "levelup", "nedb", "lowdb", "better-sqlite3",
    "knex", "typeorm", "prisma", "drizzle-orm", "objection",
    "graphql", "apollo-server", "type-graphql", "nexus",
    "grpc", "protobufjs", "thrift", "avsc",
    "amqplib", "kafkajs", "mqtt", "nats", "zeromq",
    "nodemailer", "mailgun-js", "postmark", "ses",
    "twit", "discord.js", "slack-bolt", "telegraf",
    "puppeteer-core", "playwright", "selenium-webdriver", "webdriverio",
    "cypress", "nightwatch", "testcafe", "detox",
    "supertest", "nock", "msw", "faker", "chance",
    "factory-girl", "fishery", "test-data-bot",
    "nyc", "c8", "istanbul", "codecov",
    "husky", "lint-staged", "commitlint", "conventional-changelog",
    "semantic-release", "standard-version", "release-it",
    "lerna", "nx", "turbo", "rush",
    "tsconfig-paths", "module-alias", "esm", "tsx",
    "ts-node", "ts-jest", "babel-jest",
    "source-map-support", "stacktrace-js", "error-stack-parser",
    "depd", "http-errors", "statuses", "content-type",
    "content-disposition", "accepts", "negotiator", "vary",
    "etag", "fresh", "range-parser", "raw-body",
    "type-is", "media-typer", "mime", "mime-types",
    "send", "serve-static", "finalhandler", "on-finished",
    "destroy", "unpipe", "ee-first", "merge-descriptors",
    "utils-merge", "path-to-regexp", "methods", "parseurl",
    "qs", "querystring", "url-parse", "normalize-url",
    "is-url", "valid-url", "encodeurl", "escape-html",
    "cookie", "cookie-signature", "csrf", "csurf",
    "express-rate-limit", "rate-limiter-flexible", "bottleneck",
    "p-limit", "p-queue", "p-retry", "p-map",
    "p-all", "p-settle", "p-props", "p-series",
    "delay", "ms", "pretty-ms", "humanize-duration",
    "bytes", "pretty-bytes", "filesize",
    "nanoid", "shortid", "cuid", "ulid", "ksuid",
    "lodash.get", "lodash.set", "lodash.merge", "lodash.clonedeep",
    "lodash.debounce", "lodash.throttle", "lodash.isequal",
    "deepmerge", "deep-equal", "fast-deep-equal",
    "object-assign", "object-keys", "has",
    "is-plain-object", "is-buffer", "is-stream",
    "is-promise", "is-generator-function", "is-async-function",
    "inherits", "util-deprecate", "safe-buffer",
    "string-width", "strip-ansi", "ansi-regex", "ansi-styles",
    "supports-color", "color-convert", "color-name",
    "wrap-ansi", "cliui", "y18n", "get-caller-file",
    "require-directory", "which-module", "camelcase", "decamelize",
    "find-up", "locate-path", "path-exists", "pkg-dir",
    "resolve-from", "import-from", "parent-module", "callsites",
    "resolve", "browser-resolve", "enhanced-resolve",
    "normalize-path", "upath", "slash", "globby",
    "fast-glob", "dir-glob", "ignore", "gitignore-parser",
    "execa", "cross-spawn", "which", "npm-run-path",
    "path-key", "human-signals", "signal-exit", "strip-final-newline",
]


def _caminho_json() -> Path:
    return config.DIR_DADOS / "top_500_npm.json"


def obter_top_500() -> list[str]:
    """
    Retorna a lista dos 500 pacotes mais populares.
    Usa cache em memoria (TTL 24h) -> arquivo JSON -> fallback hardcoded.
    """
    global _cache

    agora = time.time()
    if _cache["pacotes"] and (agora - _cache["timestamp"]) < _CACHE_TTL:
        return _cache["pacotes"]

    caminho = _caminho_json()
    if caminho.exists():
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            pacotes = [p["nome"] if isinstance(p, dict) else p for p in dados]
            if pacotes:
                _cache = {"pacotes": pacotes[:500], "timestamp": agora}
                log.info("top_500_carregado_arquivo", total=len(pacotes))
                return _cache["pacotes"]
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("top_500_arquivo_invalido", erro=str(e))

    _cache = {"pacotes": _TOP_500_FALLBACK[:500], "timestamp": agora}
    log.info("top_500_fallback", total=len(_cache["pacotes"]))
    return _cache["pacotes"]


def atualizar_top_500_npm() -> list[str]:
    """
    Busca os top-500 pacotes mais baixados no ultimo mes via npm API.
    Salva em data/top_500_npm.json.
    """
    url = "https://api.npmjs.org/downloads/point/last-month"

    top = obter_top_500()

    resultados = []
    with httpx.Client(timeout=30.0) as client:
        for i in range(0, len(top), 128):
            batch = top[i : i + 128]
            nomes = ",".join(batch)
            try:
                resp = client.get(f"{url}/{nomes}")
                if resp.status_code == 200:
                    dados = resp.json()
                    for nome, info in dados.items():
                        if isinstance(info, dict) and "downloads" in info:
                            resultados.append({
                                "nome": nome,
                                "downloads": info["downloads"],
                            })
            except Exception as e:
                log.warning("top_500_api_erro", erro=str(e))

    resultados.sort(key=lambda x: x["downloads"], reverse=True)
    top_500 = resultados[:500]

    caminho = _caminho_json()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(top_500, indent=2), encoding="utf-8")

    nomes = [p["nome"] for p in top_500]
    global _cache
    _cache = {"pacotes": nomes, "timestamp": time.time()}
    log.info("top_500_atualizado", total=len(nomes))
    return nomes
