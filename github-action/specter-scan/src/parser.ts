/**
 * Parser de dependencias para o Specter Scan.
 * Extrai nomes de pacotes de package.json, requirements.txt e pyproject.toml.
 */

import * as fs from 'fs';
import * as path from 'path';

/** Representa uma dependencia com nome, versao opcional e ecossistema */
export interface Dependencia {
  name: string;
  version?: string;
  ecosystem: string;
}

/**
 * Extrai dependencias e devDependencies do package.json.
 * Retorna lista de { name, version, ecosystem: 'npm' }
 */
export function parsePackageJson(conteudo: string): Dependencia[] {
  const deps: Dependencia[] = [];
  try {
    const pkg = JSON.parse(conteudo) as Record<string, unknown>;
    const allDeps: Record<string, string> = {
      ...((pkg.dependencies as Record<string, string>) || {}),
      ...((pkg.devDependencies as Record<string, string>) || {}),
      ...((pkg.optionalDependencies as Record<string, string>) || {}),
    };
    for (const [name, version] of Object.entries(allDeps)) {
      if (name && typeof version === 'string') {
        deps.push({
          name,
          version: version.replace(/^[\^~]/, '').split('-')[0], // remove ^ ~ e sufixos
          ecosystem: 'npm',
        });
      }
    }
  } catch {
    // JSON invalido - retorna vazio
  }
  return deps;
}

/**
 * Extrai nomes de pacotes do requirements.txt.
 * Suporta formatos: pacote, pacote==1.0, pacote>=1.0, pacote[extra], -r outro.txt
 */
export function parseRequirements(conteudo: string): Dependencia[] {
  const deps: Dependencia[] = [];
  const linhas = conteudo.split(/\r?\n/);
  for (let linha of linhas) {
    linha = linha.trim();
    // Ignora comentarios, linhas vazias, -r, -e, --extra-index-url
    if (
      !linha ||
      linha.startsWith('#') ||
      linha.startsWith('-r ') ||
      linha.startsWith('-e ') ||
      linha.startsWith('--')
    ) {
      continue;
    }
    // Remove comentarios inline
    const idxHash = linha.indexOf('#');
    if (idxHash >= 0) {
      linha = linha.substring(0, idxHash).trim();
    }
    // Extrai nome do pacote (antes de ==, >=, <=, ~=, [, etc)
    const match = linha.match(/^([a-zA-Z0-9_-]+)/);
    if (match) {
      const name = match[1].replace(/_/g, '-').toLowerCase();
      let version: string | undefined;
      const eqMatch = linha.match(/[=~<>]+(.+?)(?:\s|$|\[)/);
      if (eqMatch) {
        version = eqMatch[1].trim();
      }
      deps.push({ name, version, ecosystem: 'pypi' });
    }
  }
  return deps;
}

/**
 * Parsing basico de pyproject.toml para extrair dependencias.
 * Suporta [project.dependencies] e [tool.poetry.dependencies]
 */
export function parsePyprojectToml(conteudo: string): Dependencia[] {
  const deps: Dependencia[] = [];
  try {
    // Regex simples para arrays de dependencias no formato TOML
    const projectMatch = conteudo.match(
      /\[project\]\s*dependencies\s*=\s*\[([\s\S]*?)\](?=\s*\[|\s*$)/m
    );
    const poetryMatch = conteudo.match(
      /\[tool\.poetry\.dependencies\]\s*([\s\S]*?)(?=\[tool\.poetry|\s*$)/m
    );

    const extrairDeArray = (bloco: string) => {
      const itens = bloco.match(/["']([^"']+)["']/g) || [];
      for (const item of itens) {
        const limpo = item.replace(/^["']|["']$/g, '');
        const nameMatch = limpo.match(/^([a-zA-Z0-9_-]+)/);
        if (nameMatch) {
          const name = nameMatch[1].replace(/_/g, '-').toLowerCase();
          const versionMatch = limpo.match(/[=~<>]+(.+)$/);
          deps.push({
            name,
            version: versionMatch ? versionMatch[1].trim() : undefined,
            ecosystem: 'pypi',
          });
        }
      }
    };

    const extrairDePoetry = (bloco: string) => {
      const linhas = bloco.split('\n');
      for (const linha of linhas) {
        const match = linha.match(/^([a-zA-Z0-9_-]+)\s*=\s*["']([^"']*)["']/);
        if (match && match[1] !== 'python') {
          deps.push({
            name: match[1].replace(/_/g, '-').toLowerCase(),
            version: match[2] || undefined,
            ecosystem: 'pypi',
          });
        }
      }
    };

    if (projectMatch) {
      extrairDeArray(projectMatch[1]);
    }
    if (poetryMatch) {
      extrairDePoetry(poetryMatch[1]);
    }
  } catch {
    // TOML invalido ou formato nao suportado
  }
  return deps;
}

/**
 * Coleta todas as dependencias do workspace baseado nos ecossistemas.
 * Busca package.json, requirements.txt e pyproject.toml no diretorio raiz.
 */
export function coletarDependencias(
  workspaceRoot: string,
  ecosystems: string[]
): Dependencia[] {
  const todos: Dependencia[] = [];
  const ecoSet = new Set(ecosystems.map((e) => e.trim().toLowerCase()));

  if (ecoSet.has('npm')) {
    const pkgPath = path.join(workspaceRoot, 'package.json');
    if (fs.existsSync(pkgPath)) {
      const conteudo = fs.readFileSync(pkgPath, 'utf-8');
      todos.push(...parsePackageJson(conteudo));
    }
  }

  if (ecoSet.has('pypi')) {
    const reqPath = path.join(workspaceRoot, 'requirements.txt');
    const pyPath = path.join(workspaceRoot, 'pyproject.toml');
    if (fs.existsSync(reqPath)) {
      const conteudo = fs.readFileSync(reqPath, 'utf-8');
      todos.push(...parseRequirements(conteudo));
    }
    if (fs.existsSync(pyPath)) {
      const conteudo = fs.readFileSync(pyPath, 'utf-8');
      todos.push(...parsePyprojectToml(conteudo));
    }
  }

  // Remove duplicatas por nome+ecosystem
  const vistos = new Set<string>();
  return todos.filter((d) => {
    const key = `${d.ecosystem}:${d.name}`;
    if (vistos.has(key)) return false;
    vistos.add(key);
    return true;
  });
}
