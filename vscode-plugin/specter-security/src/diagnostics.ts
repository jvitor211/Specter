/**
 * Mapeamento de resultados do scan para diagnósticos visuais no VS Code.
 */

import * as vscode from 'vscode';

import type { ResponseScan } from './scanner';

/** Mapeamento nome do pacote -> posição no arquivo (linha, coluna) */
export type PosicoesPacotes = Map<string, { line: number; character: number }>;

/**
 * Atualiza a coleção de diagnósticos com base nos resultados do scan.
 * Score > 0.7: Error (Risco alto)
 * Score 0.3-0.7: Warning (Revisão recomendada)
 * Score < 0.3: sem diagnóstico
 */
export function updateDiagnostics(
  collection: vscode.DiagnosticCollection,
  uri: vscode.Uri,
  results: ResponseScan | null,
  posicoes: PosicoesPacotes,
  riskThreshold: number
): void {
  if (!results) {
    collection.delete(uri);
    return;
  }

  const diagnostics: vscode.Diagnostic[] = [];

  for (const pkg of results.packages) {
    const pos = posicoes.get(pkg.name);
    if (!pos) continue;

    const range = new vscode.Range(pos.line, pos.character, pos.line, pos.character + pkg.name.length);
    const score = pkg.score;

    if (score > 0.7) {
      diagnostics.push({
        range,
        message: `Specter: Risco alto (score ${score.toFixed(2)}) — ${pkg.recommendation}`,
        severity: vscode.DiagnosticSeverity.Error,
        source: 'specter',
      });
    } else if (score >= riskThreshold && score <= 0.7) {
      diagnostics.push({
        range,
        message: `Specter: Revisão recomendada (score ${score.toFixed(2)}) — ${pkg.recommendation}`,
        severity: vscode.DiagnosticSeverity.Warning,
        source: 'specter',
      });
    }
  }

  collection.set(uri, diagnostics);
}

/**
 * Cria um HoverProvider que exibe score e top_reasons ao passar o mouse.
 */
export function createHoverProvider(
  getResults: () => Map<string, ResponseScan | null>
): vscode.Disposable {
  return vscode.languages.registerHoverProvider(
    [{ language: 'json', pattern: '**/package.json' }, { pattern: '**/requirements.txt' }],
    {
      provideHover(document, position) {
        const uri = document.uri.toString();
        const results = getResults();
        const scan = results.get(uri);
        if (!scan) return null;

        const line = document.lineAt(position.line).text;
        for (const pkg of scan.packages) {
          const idx = line.includes(`"${pkg.name}"`) ? line.indexOf(`"${pkg.name}"`) : line.indexOf(pkg.name);
          if (idx >= 0 && position.character >= idx && position.character <= idx + pkg.name.length) {
            const reasons = pkg.top_reasons.length > 0
              ? pkg.top_reasons.join('\n• ')
              : 'Nenhum motivo específico';
            const md = new vscode.MarkdownString();
            md.appendMarkdown(`**Specter** — ${pkg.name}\n\n`);
            md.appendMarkdown(`Score: **${pkg.score.toFixed(2)}** | Verdict: ${pkg.verdict}\n\n`);
            md.appendMarkdown(`**Principais motivos:**\n• ${reasons}\n\n`);
            md.appendMarkdown(pkg.recommendation);
            return new vscode.Hover(md);
          }
        }
        return null;
      },
    }
  );
}
