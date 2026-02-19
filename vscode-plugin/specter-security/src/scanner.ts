/**
 * Lógica principal de escaneamento de pacotes via API Specter.
 */

import * as https from 'https';
import * as http from 'http';

/** Pacote extraído de arquivo de dependências */
export interface PacoteExtraido {
  name: string;
  version?: string;
  ecosystem: 'npm' | 'pypi';
}

/** Resultado do scan de um pacote (formato da API Specter) */
export interface ResultadoPacote {
  name: string;
  ecosystem: string;
  version: string | null;
  score: number;
  verdict: string;
  top_reasons: string[];
  recommendation: string;
}

/** Resposta completa da API POST /v1/scan */
export interface ResponseScan {
  session_id: string;
  packages: ResultadoPacote[];
  total_scanned: number;
  total_flagged: number;
  response_time_ms: number;
}

/**
 * Extrai nomes de pacotes de package.json ou requirements.txt.
 */
export function parseDependencyFile(
  content: string,
  filename: string
): PacoteExtraido[] {
  const pacotes: PacoteExtraido[] = [];

  if (filename.endsWith('package.json')) {
    try {
      const pkg = JSON.parse(content);
      const deps = {
        ...pkg.dependencies,
        ...pkg.devDependencies,
        ...pkg.optionalDependencies,
      };
      for (const [name, version] of Object.entries(deps || {})) {
        if (typeof version === 'string') {
          pacotes.push({
            name,
            version: version.replace(/^[\^~]/, '').split('-')[0],
            ecosystem: 'npm',
          });
        }
      }
    } catch {
      return [];
    }
  } else if (filename.endsWith('requirements.txt')) {
    const lines = content.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const match = trimmed.match(/^([a-zA-Z0-9_-]+)(?:==|>=|<=|>|<|~=)?([\d.]*)?/);
      if (match) {
        pacotes.push({
          name: match[1],
          version: match[2] || undefined,
          ecosystem: 'pypi',
        });
      }
    }
  }

  return pacotes;
}

/** Retorno de parseDependencyFileWithPositions */
export interface ParseResult {
  pacotes: PacoteExtraido[];
  posicoes: Map<string, { line: number; character: number }>;
}

/**
 * Extrai pacotes e suas posições (linha, coluna) no arquivo.
 */
export function parseDependencyFileWithPositions(
  content: string,
  filename: string
): ParseResult {
  const posicoes = new Map<string, { line: number; character: number }>();
  const pacotes: PacoteExtraido[] = [];

  if (filename.endsWith('package.json')) {
    try {
      const pkg = JSON.parse(content);
      const deps = {
        ...pkg.dependencies,
        ...pkg.devDependencies,
        ...pkg.optionalDependencies,
      };
      const lines = content.split('\n');
      for (const [name, version] of Object.entries(deps || {})) {
        if (typeof version === 'string') {
          pacotes.push({
            name,
            version: version.replace(/^[\^~]/, '').split('-')[0],
            ecosystem: 'npm',
          });
          for (let i = 0; i < lines.length; i++) {
            const idx = lines[i].indexOf(`"${name}"`);
            if (idx >= 0) {
              posicoes.set(name, { line: i, character: idx + 1 });
              break;
            }
          }
        }
      }
    } catch {
      return { pacotes: [], posicoes };
    }
  } else if (filename.endsWith('requirements.txt')) {
    const lines = content.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const match = trimmed.match(/^([a-zA-Z0-9_-]+)(?:==|>=|<=|>|<|~=)?([\d.]*)?/);
      if (match) {
        const name = match[1];
        pacotes.push({
          name,
          version: match[2] || undefined,
          ecosystem: 'pypi',
        });
        const charIdx = lines[i].indexOf(name);
        posicoes.set(name, { line: i, character: charIdx >= 0 ? charIdx : 0 });
      }
    }
  }

  return { pacotes, posicoes };
}

/**
 * Chama a API Specter POST /v1/scan com os pacotes extraídos.
 * Retorna os resultados ou null em caso de erro.
 */
export async function scanPackages(
  pacotes: PacoteExtraido[],
  apiUrl: string,
  apiKey: string
): Promise<ResponseScan | null> {
  if (pacotes.length === 0) return null;
  if (!apiKey || apiKey.trim() === '') return null;

  const url = new URL(apiUrl);
  const isHttps = url.protocol === 'https:';
  const path = `${url.pathname.replace(/\/$/, '')}/v1/scan`;

  const body = JSON.stringify({
    packages: pacotes.map((p) => ({
      name: p.name,
      version: p.version || null,
      ecosystem: p.ecosystem,
    })),
  });

  const options = {
    hostname: url.hostname,
    port: url.port || (isHttps ? 443 : 80),
    path,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(body),
      'X-Specter-Key': apiKey,
    },
  };

  return new Promise((resolve) => {
    const req = (isHttps ? https : http).request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          if (res.statusCode === 200) {
            resolve(JSON.parse(data) as ResponseScan);
          } else {
            resolve(null);
          }
        } catch {
          resolve(null);
        }
      });
    });

    req.on('error', () => resolve(null));
    req.setTimeout(10000, () => {
      req.destroy();
      resolve(null);
    });
    req.write(body);
    req.end();
  });
}
