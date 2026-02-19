/**
 * Specter Security Scan - GitHub Action
 * Escaneia dependencias via API Specter e falha se houver pacotes maliciosos.
 */

import * as core from '@actions/core';
import * as github from '@actions/github';
import { coletarDependencias, Dependencia } from './parser';

const MAX_PACOTES_POR_REQUEST = 50;

interface ResultadoPacote {
  name: string;
  ecosystem: string;
  version: string | null;
  score: number;
  verdict: string;
  top_reasons: string[];
  recommendation: string;
}

interface ResponseScan {
  session_id: string;
  packages: ResultadoPacote[];
  total_scanned: number;
  total_flagged: number;
  response_time_ms: number;
}

/** Chama a API Specter POST /v1/scan em lotes de ate 50 pacotes */
async function chamarSpecterApi(
  apiUrl: string,
  apiKey: string,
  pacotes: Array<{ name: string; version?: string; ecosystem: string }>
): Promise<ResponseScan> {
  const url = `${apiUrl.replace(/\/$/, '')}/v1/scan`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Specter-Key': apiKey,
    },
    body: JSON.stringify({ packages: pacotes }),
  });

  if (!res.ok) {
    const texto = await res.text();
    throw new Error(`Specter API erro ${res.status}: ${texto}`);
  }

  return (await res.json()) as ResponseScan;
}

/** Escaneia todos os pacotes em lotes e retorna resultados concatenados */
async function escanearTodos(
  apiUrl: string,
  apiKey: string,
  deps: Dependencia[]
): Promise<ResultadoPacote[]> {
  const todos: ResultadoPacote[] = [];
  for (let i = 0; i < deps.length; i += MAX_PACOTES_POR_REQUEST) {
    const lote = deps.slice(i, i + MAX_PACOTES_POR_REQUEST);
    const payload = lote.map((d) => ({
      name: d.name,
      version: d.version,
      ecosystem: d.ecosystem,
    }));
    const resp = await chamarSpecterApi(apiUrl, apiKey, payload);
    todos.push(...resp.packages);
  }
  return todos;
}

/** Gera tabela markdown com os resultados */
function gerarTabelaMarkdown(resultados: ResultadoPacote[]): string {
  const linhas = [
    '| Pacote | Ecossistema | Score | Verdict | Motivos |',
    '|--------|-------------|-------|---------|--------|',
  ];
  for (const r of resultados) {
    const motivos = (r.top_reasons || []).slice(0, 2).join('; ') || '-';
    linhas.push(
      `| ${r.name} | ${r.ecosystem} | ${r.score.toFixed(2)} | ${r.verdict} | ${motivos} |`
    );
  }
  return linhas.join('\n');
}

/** Comenta na PR com os resultados do scan */
async function comentarNaPR(
  token: string,
  body: string,
  replaceExisting = true
): Promise<void> {
  const octokit = github.getOctokit(token);
  const { owner, repo, number } = github.context.issue;

  if (!number) {
    core.info('Nao e um evento de PR - comentario ignorado.');
    return;
  }

  const comentarioIdentificador = '<!-- specter-scan -->';

  if (replaceExisting) {
    const { data: comentarios } = await octokit.rest.issues.listComments({
      owner,
      repo,
      issue_number: number,
    });
    const existente = comentarios.find((c) =>
      (c.body || '').includes(comentarioIdentificador)
    );
    if (existente) {
      await octokit.rest.issues.updateComment({
        owner,
        repo,
        comment_id: existente.id,
        body: `${comentarioIdentificador}\n\n${body}`,
      });
      return;
    }
  }

  await octokit.rest.issues.createComment({
    owner,
    repo,
    issue_number: number,
    body: `${comentarioIdentificador}\n\n${body}`,
  });
}

async function main(): Promise<void> {
  try {
    const apiKey = core.getInput('api_key', { required: true });
    const apiUrl =
      process.env.SPECTER_API_URL || 'https://api.specter.dev';
    const riskThreshold = parseFloat(
      core.getInput('risk_threshold') || '0.5'
    );
    const ecosystems = (core.getInput('ecosystems') || 'npm,pypi').split(',');
    const failOnReview = core.getBooleanInput('fail_on_review');
    const commentOnPr = core.getBooleanInput('comment_on_pr');

    const workspaceRoot =
      process.env.GITHUB_WORKSPACE || process.cwd();

    core.info('Coletando dependencias do repositorio...');
    const deps = coletarDependencias(workspaceRoot, ecosystems);

    if (deps.length === 0) {
      core.info('Nenhuma dependencia encontrada (package.json, requirements.txt ou pyproject.toml).');
      core.setOutput('packages_scanned', '0');
      core.setOutput('packages_flagged', '0');
      core.setOutput('report_url', '');
      return;
    }

    core.info(`Encontradas ${deps.length} dependencias. Escaneando via Specter API...`);
    const resultados = await escanearTodos(apiUrl, apiKey, deps);

    const flagged = resultados.filter(
      (r) =>
        r.score > riskThreshold ||
        r.verdict === 'blocked' ||
        (failOnReview && r.verdict === 'review')
    );

    core.setOutput('packages_scanned', String(resultados.length));
    core.setOutput('packages_flagged', String(flagged.length));
    core.setOutput('report_url', ''); // API pode retornar URL futuramente

    if (commentOnPr && github.context.eventName === 'pull_request') {
      const token = core.getInput('GITHUB_TOKEN') || process.env.GITHUB_TOKEN;
      if (token) {
        const titulo = flagged.length > 0
          ? '## Specter Security Scan – Pacotes sinalizados'
          : '## Specter Security Scan – Nenhum risco detectado';
        const tabela = gerarTabelaMarkdown(resultados);
        const body = `${titulo}\n\n**Escaneados:** ${resultados.length} | **Sinalizados:** ${flagged.length}\n\n${tabela}`;
        await comentarNaPR(token, body);
      } else {
        core.warning('GITHUB_TOKEN nao disponivel - comentario na PR ignorado.');
      }
    }

    if (flagged.length > 0) {
      core.setFailed(
        `Specter encontrou ${flagged.length} pacote(s) com risco acima do threshold (${riskThreshold}): ${flagged.map((f) => f.name).join(', ')}`
      );
    } else {
      core.info('Scan concluido. Nenhum pacote malicioso detectado.');
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    core.setFailed(`Erro no Specter Scan: ${msg}`);
  }
}

main();
