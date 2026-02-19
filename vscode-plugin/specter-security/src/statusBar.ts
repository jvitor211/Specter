/**
 * Gerenciamento da barra de status do Specter.
 */

import * as vscode from 'vscode';

let statusBarItem: vscode.StatusBarItem | undefined;

/**
 * Cria o item da barra de status (chamado na ativação).
 */
export function createStatusBar(): vscode.StatusBarItem {
  if (!statusBarItem) {
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  }
  return statusBarItem;
}

/**
 * Exibe "Specter: Escaneando..." durante o scan.
 */
export function showScanning(): void {
  if (statusBarItem) {
    statusBarItem.text = '$(sync~spin) Specter: Escaneando...';
    statusBarItem.show();
  }
}

/**
 * Exibe resultado após o scan: "X clean" ou "X sinalizados".
 * Clique abre o painel de saída.
 */
export function showResult(totalScanned: number, totalFlagged: number): void {
  if (!statusBarItem) return;

  if (totalFlagged > 0) {
    statusBarItem.text = `$(warning) Specter: ${totalFlagged} sinalizados`;
    statusBarItem.tooltip = `${totalFlagged} de ${totalScanned} pacotes sinalizados. Clique para ver detalhes.`;
  } else {
    statusBarItem.text = `$(check) Specter: ${totalScanned} clean`;
    statusBarItem.tooltip = `${totalScanned} pacotes escaneados. Nenhum sinalizado.`;
  }

  statusBarItem.command = 'specter.showOutput';
  statusBarItem.show();
}

/**
 * Oculta a barra de status.
 */
export function hide(): void {
  if (statusBarItem) {
    statusBarItem.hide();
  }
}

/**
 * Exibe mensagem de erro na barra de status.
 */
export function showError(message: string): void {
  if (statusBarItem) {
    statusBarItem.text = `$(error) Specter: Erro`;
    statusBarItem.tooltip = message;
    statusBarItem.show();
  }
}
