import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatarNumero(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("pt-BR");
}

export function corVerdict(verdict: string): string {
  switch (verdict) {
    case "blocked":
      return "text-risco-alto";
    case "review":
      return "text-risco-medio";
    case "safe":
      return "text-risco-baixo";
    default:
      return "text-texto-muted";
  }
}

export function badgeVerdict(verdict: string): string {
  switch (verdict) {
    case "blocked":
      return "badge-risco-alto";
    case "review":
      return "badge-risco-medio";
    case "safe":
      return "badge-risco-baixo";
    default:
      return "bg-borda text-texto-muted px-2.5 py-0.5 rounded-full text-xs";
  }
}

export function traduzirVerdict(verdict: string): string {
  switch (verdict) {
    case "blocked":
      return "Bloqueado";
    case "review":
      return "Revisar";
    case "safe":
      return "Seguro";
    case "unknown":
      return "Desconhecido";
    case "error":
      return "Erro";
    default:
      return verdict;
  }
}
