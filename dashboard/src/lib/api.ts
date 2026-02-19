/**
 * Cliente para a Specter API.
 * Gerencia API key via localStorage e faz chamadas autenticadas.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function obterApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("specter_api_key");
}

export function salvarApiKey(key: string): void {
  localStorage.setItem("specter_api_key", key);
}

export function removerApiKey(): void {
  localStorage.removeItem("specter_api_key");
}

async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const key = obterApiKey();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (key) {
    headers["X-Specter-Key"] = key;
  }

  const resp = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!resp.ok) {
    const erro = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(erro.detail || `Erro ${resp.status}`);
  }

  return resp.json();
}

// --- Tipos ---

export interface PacoteScan {
  name: string;
  version?: string;
  ecosystem: string;
}

export interface ResultadoPacote {
  name: string;
  ecosystem: string;
  version: string | null;
  score: number;
  verdict: string;
  top_reasons: string[];
  recommendation: string;
}

export interface RespostaScan {
  session_id: string;
  packages: ResultadoPacote[];
  total_scanned: number;
  total_flagged: number;
  response_time_ms: number;
}

export interface HealthStatus {
  status: string;
  versao_api: string;
  modelo_carregado: boolean;
  timestamp: number;
}

export interface UsoAPI {
  email: string;
  tier: string;
  requisicoes_mes: number;
  limite_mes: number | null;
  criado_em: string;
}

export interface PacoteDetalhado {
  id: number;
  nome: string;
  ecossistema: string;
  descricao: string | null;
  url_repositorio: string | null;
  criado_em: string | null;
  atualizado_em: string | null;
  versoes: {
    versao: string;
    publicado_em: string | null;
    tem_postinstall: boolean;
    tem_preinstall: boolean;
    contagem_mantenedores: number;
  }[];
  features: {
    score_risco: number | null;
    score_typosquatting: number | null;
    tem_github: boolean;
    estrelas_github: number | null;
    provavel_typosquat: boolean;
    computado_em: string | null;
  } | null;
}

// --- Chamadas ---

export async function scanPacotes(
  pacotes: PacoteScan[]
): Promise<RespostaScan> {
  return fetchAPI<RespostaScan>("/v1/scan", {
    method: "POST",
    body: JSON.stringify({ packages: pacotes }),
  });
}

export async function obterHealth(): Promise<HealthStatus> {
  return fetchAPI<HealthStatus>("/v1/health");
}

export async function obterUso(): Promise<UsoAPI> {
  return fetchAPI<UsoAPI>("/v1/keys/usage");
}

export async function obterPacote(
  ecossistema: string,
  nome: string
): Promise<PacoteDetalhado> {
  return fetchAPI<PacoteDetalhado>(`/v1/package/${ecossistema}/${nome}`);
}

export async function criarChave(
  email: string
): Promise<{ api_key: string; tier: string; message: string }> {
  return fetchAPI("/v1/keys/create", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export interface UpgradeResponse {
  tier: string;
  message: string;
  checkout_url: string | null;
}

export async function upgradarTier(
  tier: string,
  plan: string = "pro_monthly"
): Promise<UpgradeResponse> {
  return fetchAPI("/v1/keys/upgrade", {
    method: "POST",
    body: JSON.stringify({ tier, plan }),
  });
}

export async function criarCheckoutStripe(
  plan: string = "pro_monthly"
): Promise<{ checkout_url: string; session_id: string }> {
  return fetchAPI("/v1/stripe/checkout", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export async function obterPortalStripe(): Promise<{ portal_url: string }> {
  return fetchAPI("/v1/stripe/portal");
}

export async function enviarFeedback(dados: {
  package: string;
  ecosystem: string;
  version?: string;
  is_false_positive: boolean;
}): Promise<{ status: string; message: string }> {
  return fetchAPI("/v1/feedback", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}

// --- Stats (dashboard) ---

export interface DistribuicaoItem {
  name: string;
  value: number;
  cor: string;
}

export interface ScanRecente {
  pacote: string;
  ecossistema: string;
  score: number;
  verdict: string;
  criado_em: string | null;
}

export interface ScanDia {
  dia: string;
  scans: number;
  flagged: number;
}

export interface StatsResponse {
  total_pacotes: number;
  total_scans_mes: number;
  total_sinalizados: number;
  taxa_seguranca: number;
  distribuicao: DistribuicaoItem[];
  ultimos_scans: ScanRecente[];
  scans_por_dia: ScanDia[];
}

export async function obterStats(): Promise<StatsResponse> {
  const resp = await fetch(
    `${API_BASE}/v1/stats`,
    { headers: { "Content-Type": "application/json" } }
  );
  if (!resp.ok) {
    throw new Error(`Erro ${resp.status}`);
  }
  return resp.json();
}
