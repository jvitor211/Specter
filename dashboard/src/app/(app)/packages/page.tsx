"use client";

import { useState } from "react";
import { Search, ExternalLink, AlertTriangle, Shield, Lock } from "lucide-react";
import { obterPacote, type PacoteDetalhado } from "@/lib/api";
import { traduzirVerdict, badgeVerdict } from "@/lib/utils";
import { useTier } from "@/lib/tier-context";
import Link from "next/link";

export default function PackagesPage() {
  const { isFree } = useTier();
  const [busca, setBusca] = useState("");
  const [ecossistema, setEcossistema] = useState("npm");
  const [pacote, setPacote] = useState<PacoteDetalhado | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");

  async function handleBusca(e: React.FormEvent) {
    e.preventDefault();
    if (!busca.trim()) return;

    setCarregando(true);
    setErro("");
    setPacote(null);

    try {
      const resultado = await obterPacote(ecossistema, busca.trim());
      setPacote(resultado);
    } catch (err: any) {
      setErro(err.message || "Pacote nao encontrado");
    } finally {
      setCarregando(false);
    }
  }

  function scoreColor(score: number | null | undefined): string {
    if (score == null) return "text-texto-muted";
    if (score >= 0.7) return "text-risco-alto";
    if (score >= 0.3) return "text-risco-medio";
    return "text-risco-baixo";
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-titulo text-2xl font-bold">Explorador de Pacotes</h1>
        <p className="text-texto-muted text-sm mt-1">
          Busque pacotes npm ou PyPI para ver score de risco e historico
        </p>
      </div>

      <form onSubmit={handleBusca} className="flex gap-3">
        <select
          value={ecossistema}
          onChange={(e) => setEcossistema(e.target.value)}
          className="bg-fundo border border-borda rounded-lg px-4 py-2.5 text-sm text-texto-primario focus:outline-none focus:border-accent"
        >
          <option value="npm">npm</option>
          <option value="pypi">PyPI</option>
        </select>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-texto-muted" />
          <input
            type="text"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Nome do pacote (ex: lodash, express, requests)"
            className="input-field pl-10"
          />
        </div>
        <button type="submit" disabled={carregando} className="btn-primary">
          {carregando ? "Buscando..." : "Buscar"}
        </button>
      </form>

      {erro && (
        <div className="card border-risco-alto/30">
          <p className="text-risco-alto text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            {erro}
          </p>
        </div>
      )}

      {pacote && (
        <div className="space-y-6">
          <div className="card">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h2 className="font-titulo text-xl font-bold">{pacote.nome}</h2>
                  <span className="bg-borda text-texto-muted px-2.5 py-0.5 rounded-full text-xs">
                    {pacote.ecossistema}
                  </span>
                </div>
                {pacote.descricao && (
                  <p className="text-texto-secundario text-sm max-w-2xl">
                    {pacote.descricao}
                  </p>
                )}
              </div>

              {pacote.features && (
                <div className="text-right">
                  <p className="text-texto-muted text-xs mb-1">Score de Risco</p>
                  <p
                    className={`text-3xl font-titulo font-bold ${scoreColor(pacote.features.score_risco)}`}
                  >
                    {pacote.features.score_risco != null
                      ? pacote.features.score_risco.toFixed(2)
                      : "N/A"}
                  </p>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-borda">
              <div>
                <p className="text-texto-muted text-xs">Criado em</p>
                <p className="text-sm mt-0.5">
                  {pacote.criado_em
                    ? new Date(pacote.criado_em).toLocaleDateString("pt-BR")
                    : "N/A"}
                </p>
              </div>
              <div>
                <p className="text-texto-muted text-xs">Versoes</p>
                <p className="text-sm mt-0.5">{pacote.versoes.length}</p>
              </div>
              <div>
                <p className="text-texto-muted text-xs">GitHub</p>
                <p className="text-sm mt-0.5">
                  {pacote.features?.tem_github ? (
                    <span className="text-risco-baixo flex items-center gap-1">
                      <Shield className="w-3.5 h-3.5" /> Sim
                      {pacote.features.estrelas_github != null &&
                        ` (${pacote.features.estrelas_github} estrelas)`}
                    </span>
                  ) : (
                    <span className="text-texto-muted">Nao</span>
                  )}
                </p>
              </div>
              <div>
                <p className="text-texto-muted text-xs">Typosquatting</p>
                <p className="text-sm mt-0.5">
                  {pacote.features?.provavel_typosquat ? (
                    <span className="text-risco-alto flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" /> Provavel
                      {pacote.features.score_typosquatting != null &&
                        ` (${pacote.features.score_typosquatting.toFixed(0)}%)`}
                    </span>
                  ) : (
                    <span className="text-texto-muted">
                      Nao
                      {pacote.features?.score_typosquatting != null &&
                        ` (${pacote.features.score_typosquatting.toFixed(0)}%)`}
                    </span>
                  )}
                </p>
              </div>
            </div>

            {pacote.url_repositorio && (
              <a
                href={pacote.url_repositorio}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-accent text-xs mt-4 hover:underline"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                {pacote.url_repositorio}
              </a>
            )}
          </div>

          {/* LLM Deep Analysis — Pro only */}
          <div className="card relative overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-titulo font-semibold text-sm">
                Analise LLM Profunda
              </h3>
              {isFree && (
                <span className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-accent">
                  <Lock className="w-3 h-3" /> Pro
                </span>
              )}
            </div>
            {isFree ? (
              <div className="relative">
                <div className="space-y-2 opacity-20 select-none pointer-events-none">
                  <div className="h-3 bg-borda rounded w-full" />
                  <div className="h-3 bg-borda rounded w-4/5" />
                  <div className="h-3 bg-borda rounded w-3/5" />
                  <div className="h-3 bg-borda rounded w-4/5" />
                  <div className="h-3 bg-borda rounded w-2/5" />
                </div>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <Lock className="w-8 h-8 text-accent/40 mb-2" />
                  <p className="text-texto-muted text-sm">
                    Analise semantica por LLM disponivel no plano Pro
                  </p>
                  <Link
                    href="/settings"
                    className="mt-2 text-xs font-mono uppercase tracking-wider text-accent hover:text-accent/80"
                  >
                    Fazer Upgrade
                  </Link>
                </div>
              </div>
            ) : (
              <p className="text-texto-muted text-sm">
                Analise LLM nao disponivel para este pacote.
                Dispare um scan com analise profunda via API.
              </p>
            )}
          </div>

          <div className="card">
            <h3 className="font-titulo font-semibold text-sm mb-4">
              Historico de Versoes ({pacote.versoes.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-texto-muted text-xs uppercase tracking-wider border-b border-borda">
                    <th className="text-left py-3 pr-4">Versao</th>
                    <th className="text-left py-3 pr-4">Publicado</th>
                    <th className="text-left py-3 pr-4">Mantenedores</th>
                    <th className="text-left py-3 pr-4">PostInstall</th>
                    <th className="text-left py-3">PreInstall</th>
                  </tr>
                </thead>
                <tbody>
                  {pacote.versoes.slice(0, 20).map((v) => (
                    <tr
                      key={v.versao}
                      className="border-b border-borda/50 hover:bg-borda/20"
                    >
                      <td className="py-2.5 pr-4 font-mono">{v.versao}</td>
                      <td className="py-2.5 pr-4 text-texto-muted">
                        {v.publicado_em
                          ? new Date(v.publicado_em).toLocaleDateString("pt-BR")
                          : "N/A"}
                      </td>
                      <td className="py-2.5 pr-4">{v.contagem_mantenedores}</td>
                      <td className="py-2.5 pr-4">
                        {v.tem_postinstall ? (
                          <span className="text-risco-alto text-xs">Sim</span>
                        ) : (
                          <span className="text-texto-muted text-xs">Nao</span>
                        )}
                      </td>
                      <td className="py-2.5">
                        {v.tem_preinstall ? (
                          <span className="text-risco-alto text-xs">Sim</span>
                        ) : (
                          <span className="text-texto-muted text-xs">Nao</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {!pacote && !erro && !carregando && (
        <div className="card text-center py-16">
          <Search className="w-12 h-12 text-borda mx-auto mb-4" />
          <p className="text-texto-muted">
            Busque um pacote para ver detalhes de seguranca
          </p>
        </div>
      )}
    </div>
  );
}
