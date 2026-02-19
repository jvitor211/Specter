/**
 * Ponto de entrada principal da extensão Specter Security.
 * Registra comandos, file watchers, diagnósticos e barra de status.
 */

import * as vscode from 'vscode';

import { createStatusBar, showScanning, showResult, showError } from './statusBar';
import { updateDiagnostics, createHoverProvider, type PosicoesPacotes } from './diagnostics';
import {
  parseDependencyFileWithPositions,
  scanPackages,
  type ResponseScan,
} from './scanner';

const SPECTER_DIAGNOSTICS = 'specter';
const DEBOUNCE_MS = 1000;

let outputChannel: vscode.OutputChannel;
const scanResults = new Map<string, ResponseScan | null>();
let debounceTimer: NodeJS.Timeout | undefined;

export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel('Specter Security');

  const diagnosticsCollection = vscode.languages.createDiagnosticCollection(SPECTER_DIAGNOSTICS);
  context.subscriptions.push(diagnosticsCollection);

  const statusBarItem = createStatusBar();
  context.subscriptions.push(statusBarItem);

  // Comando: Specter: Scan All Dependencies
  const scanAllCmd = vscode.commands.registerCommand('specter.scanAll', () => {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
      vscode.window.showWarningMessage('Specter: Abra uma pasta de workspace primeiro.');
      return;
    }
    runScanForWorkspace(workspaceFolders, diagnosticsCollection);
  });
  context.subscriptions.push(scanAllCmd);

  // Comando: Specter: Abrir painel de saída
  const showOutputCmd = vscode.commands.registerCommand('specter.showOutput', () => {
    outputChannel.show();
  });
  context.subscriptions.push(showOutputCmd);

  // Hover provider para exibir score e motivos
  const hoverProvider = createHoverProvider(() => scanResults);
  context.subscriptions.push(hoverProvider);

  // File watchers para package.json e requirements.txt
  const watcher = vscode.workspace.createFileSystemWatcher(
    '{**/package.json,**/requirements.txt}',
    false, false, false
  );

  const runScanDebounced = (uri: vscode.Uri) => {
    if (uri.fsPath.includes('node_modules')) return;

    const config = vscode.workspace.getConfiguration('specter');
    if (!config.get<boolean>('autoScan', true)) return;

    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      debounceTimer = undefined;
      runScanForFile(uri, diagnosticsCollection);
    }, DEBOUNCE_MS);
  };

  watcher.onDidChange((uri) => runScanDebounced(uri));
  watcher.onDidCreate((uri) => runScanDebounced(uri));
  context.subscriptions.push(watcher);

  // Escaneamento inicial ao abrir arquivos de dependência
  const openDocs = vscode.workspace.textDocuments;
  for (const doc of openDocs) {
    const path = doc.uri.fsPath;
    if (path.endsWith('package.json') || path.endsWith('requirements.txt')) {
      runScanDebounced(doc.uri);
    }
  }
}

/**
 * Executa scan para todos os arquivos de dependência no workspace.
 */
async function runScanForWorkspace(
  folders: readonly vscode.WorkspaceFolder[],
  collection: vscode.DiagnosticCollection
): Promise<void> {
  const config = vscode.workspace.getConfiguration('specter');
  const apiKey = config.get<string>('apiKey', '');
  if (!apiKey) {
    vscode.window.showErrorMessage(
      'Specter: Configure specter.apiKey nas configurações.'
    );
    return;
  }

  const patterns = ['**/package.json', '**/requirements.txt'];
  const excludes = '**/node_modules/**';
  const files: vscode.Uri[] = [];

  for (const folder of folders) {
    for (const pattern of patterns) {
      const found = await vscode.workspace.findFiles(
        new vscode.RelativePattern(folder, pattern),
        excludes
      );
      files.push(...found);
    }
  }

  for (const uri of files) {
    await runScanForFile(uri, collection);
  }
}

/**
 * Executa scan para um único arquivo de dependências.
 */
async function runScanForFile(
  uri: vscode.Uri,
  collection: vscode.DiagnosticCollection
): Promise<void> {
  const config = vscode.workspace.getConfiguration('specter');
  const apiKey = config.get<string>('apiKey', '');
  const apiUrl = config.get<string>('apiUrl', 'http://localhost:8000');
  const riskThreshold = config.get<number>('riskThreshold', 0.5);

  if (!apiKey) {
    outputChannel.appendLine('Specter: specter.apiKey não configurada. Ignorando scan.');
    return;
  }

  let content: string;
  try {
    const doc = await vscode.workspace.openTextDocument(uri);
    content = doc.getText();
  } catch {
    return;
  }

  const filename = uri.fsPath.split(/[/\\]/).pop() || '';
  const { pacotes, posicoes } = parseDependencyFileWithPositions(content, filename);

  if (pacotes.length === 0) {
    collection.delete(uri);
    scanResults.set(uri.toString(), null);
    return;
  }

  showScanning();
  outputChannel.appendLine(`Specter: Escaneando ${pacotes.length} pacotes em ${uri.fsPath}...`);

  // API aceita no máximo 50 pacotes por request
  const batchSize = 50;
  const allResults: ResponseScan['packages'] = [];
  let totalFlagged = 0;

  for (let i = 0; i < pacotes.length; i += batchSize) {
    const batch = pacotes.slice(i, i + batchSize);
    const result = await scanPackages(batch, apiUrl, apiKey);

    if (result) {
      allResults.push(...result.packages);
      totalFlagged += result.total_flagged;
    } else {
      outputChannel.appendLine('Specter: Erro ao chamar API. Verifique specter.apiUrl e specter.apiKey.');
      showError('Erro ao chamar API');
      collection.delete(uri);
      scanResults.set(uri.toString(), null);
      return;
    }
  }

  const response: ResponseScan = {
    session_id: '',
    packages: allResults,
    total_scanned: allResults.length,
    total_flagged: totalFlagged,
    response_time_ms: 0,
  };

  scanResults.set(uri.toString(), response);
  updateDiagnostics(collection, uri, response, posicoes, riskThreshold);
  showResult(response.total_scanned, response.total_flagged);

  outputChannel.appendLine(
    `Specter: ${response.total_scanned} pacotes escaneados, ${response.total_flagged} sinalizados.`
  );
}

export function deactivate(): void {
  if (debounceTimer) clearTimeout(debounceTimer);
}
