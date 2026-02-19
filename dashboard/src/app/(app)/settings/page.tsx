"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Key,
  Copy,
  Check,
  LogOut,
  Mail,
  BarChart3,
  Shield,
  Zap,
  Crown,
  CheckCircle,
  X,
} from "lucide-react";
import {
  obterApiKey,
  salvarApiKey,
  removerApiKey,
  obterUso,
  criarChave,
  upgradarTier,
  obterPortalStripe,
  type UsoAPI,
} from "@/lib/api";
import { useTier } from "@/lib/tier-context";

const PLAN_FEATURES = [
  { label: "VS Code plugin", free: true, pro: true, enterprise: true },
  { label: "500 scans / mes", free: true, pro: false, enterprise: false },
  { label: "Scans ilimitados", free: false, pro: true, enterprise: true },
  { label: "npm + PyPI", free: true, pro: true, enterprise: true },
  { label: "GitHub Action CI", free: false, pro: true, enterprise: true },
  { label: "API completa", free: false, pro: true, enterprise: true },
  { label: "Analise LLM profunda", free: false, pro: true, enterprise: true },
  { label: "Compliance (SOC2/LGPD)", free: false, pro: false, enterprise: true },
  { label: "Politicas customizadas", free: false, pro: false, enterprise: true },
  { label: "Integracao SIEM", free: false, pro: false, enterprise: true },
  { label: "SLA + suporte dedicado", free: false, pro: false, enterprise: true },
  { label: "Deploy on-prem", free: false, pro: false, enterprise: true },
];

function FeatureCheck({ enabled }: { enabled: boolean }) {
  return enabled ? (
    <CheckCircle className="w-4 h-4 text-risco-baixo" />
  ) : (
    <X className="w-4 h-4 text-borda" />
  );
}

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [inputKey, setInputKey] = useState("");
  const [email, setEmail] = useState("");
  const [uso, setUso] = useState<UsoAPI | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [novaChave, setNovaChave] = useState("");
  const [upgrading, setUpgrading] = useState(false);

  const { recarregar: recarregarTier } = useTier();
  const searchParams = useSearchParams();

  useEffect(() => {
    const key = obterApiKey();
    if (key) {
      setApiKey(key);
      carregarUso();
    }

    const checkout = searchParams.get("checkout");
    if (checkout === "success") {
      setMensagem("Pagamento confirmado! Seu plano Pro esta ativo.");
      recarregarTier();
      setTimeout(() => setMensagem(""), 6000);
    } else if (checkout === "cancel") {
      setMensagem("Checkout cancelado. Nenhuma cobranca realizada.");
      setTimeout(() => setMensagem(""), 4000);
    }
  }, [searchParams]);

  async function carregarUso() {
    try {
      const dados = await obterUso();
      setUso(dados);
    } catch {
      setUso(null);
    }
  }

  function handleSalvarKey() {
    if (inputKey.trim()) {
      salvarApiKey(inputKey.trim());
      setApiKey(inputKey.trim());
      setInputKey("");
      carregarUso();
      recarregarTier();
      setMensagem("API key salva com sucesso");
      setTimeout(() => setMensagem(""), 3000);
    }
  }

  function handleLogout() {
    removerApiKey();
    setApiKey("");
    setUso(null);
    recarregarTier();
    setMensagem("API key removida");
    setTimeout(() => setMensagem(""), 3000);
  }

  async function handleCriarChave(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;

    setCarregando(true);
    setMensagem("");
    setNovaChave("");

    try {
      const resultado = await criarChave(email.trim());
      setNovaChave(resultado.api_key);
      salvarApiKey(resultado.api_key);
      setApiKey(resultado.api_key);
      setMensagem(resultado.message);
      carregarUso();
      recarregarTier();
    } catch (err: any) {
      setMensagem(`Erro: ${err.message}`);
    } finally {
      setCarregando(false);
    }
  }

  async function handleUpgrade(novoTier: string, plan = "pro_monthly") {
    setUpgrading(true);
    try {
      const res = await upgradarTier(novoTier, plan);

      if (res.checkout_url) {
        window.location.href = res.checkout_url;
        return;
      }

      setMensagem(res.message);
      setTimeout(() => setMensagem(""), 4000);
      await carregarUso();
      await recarregarTier();
    } catch (err: any) {
      setMensagem(`Erro: ${err.message}`);
      setTimeout(() => setMensagem(""), 4000);
    } finally {
      setUpgrading(false);
    }
  }

  async function handleGerenciarAssinatura() {
    setUpgrading(true);
    try {
      const res = await obterPortalStripe();
      window.location.href = res.portal_url;
    } catch (err: any) {
      setMensagem(`Erro: ${err.message}`);
      setTimeout(() => setMensagem(""), 4000);
    } finally {
      setUpgrading(false);
    }
  }

  function copiarChave(texto: string) {
    navigator.clipboard.writeText(texto);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  }

  const limiteUso = uso?.limite_mes;
  const pctUso =
    limiteUso && limiteUso > 0
      ? Math.min((uso!.requisicoes_mes / limiteUso) * 100, 100)
      : 0;

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h1 className="font-titulo text-2xl font-bold">Configuracoes</h1>
        <p className="text-texto-muted text-sm mt-1">
          Gerencie sua API key e acompanhe o uso
        </p>
      </div>

      {mensagem && (
        <div className="card border-accent/30">
          <p className="text-accent text-sm">{mensagem}</p>
        </div>
      )}

      {novaChave && (
        <div className="card border-risco-medio/30 space-y-3">
          <div className="flex items-center gap-2 text-risco-medio">
            <Key className="w-4 h-4" />
            <p className="text-sm font-semibold">
              Sua nova API key (copie agora — nao sera exibida novamente):
            </p>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-fundo border border-borda rounded-lg px-4 py-2.5 text-sm font-mono break-all">
              {novaChave}
            </code>
            <button
              onClick={() => copiarChave(novaChave)}
              className="btn-ghost"
            >
              {copiado ? (
                <Check className="w-4 h-4 text-risco-baixo" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      )}

      <div className="card space-y-4">
        <h2 className="font-titulo font-semibold flex items-center gap-2">
          <Key className="w-4 h-4 text-accent" />
          API Key
        </h2>

        {apiKey ? (
          <div className="space-y-4">
            <div>
              <p className="text-texto-muted text-xs mb-1.5">Chave atual</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-fundo border border-borda rounded-lg px-4 py-2.5 text-sm font-mono">
                  {apiKey.slice(0, 12)}{"•".repeat(20)}
                </code>
                <button
                  onClick={() => copiarChave(apiKey)}
                  className="btn-ghost"
                  title="Copiar"
                >
                  {copiado ? (
                    <Check className="w-4 h-4 text-risco-baixo" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </button>
                <button
                  onClick={handleLogout}
                  className="btn-ghost text-risco-alto"
                  title="Remover"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-texto-muted text-sm">
              Insira sua API key existente ou crie uma nova.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                placeholder="spk_live_..."
                className="input-field flex-1"
              />
              <button onClick={handleSalvarKey} className="btn-primary">
                Salvar
              </button>
            </div>

            <div className="border-t border-borda pt-4">
              <p className="text-texto-muted text-xs mb-3">
                Ou crie uma nova chave gratuita:
              </p>
              <form onSubmit={handleCriarChave} className="flex gap-2">
                <div className="relative flex-1">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-texto-muted" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="seu@email.com"
                    className="input-field pl-10"
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={carregando}
                  className="btn-primary"
                >
                  {carregando ? "Criando..." : "Criar Key"}
                </button>
              </form>
            </div>
          </div>
        )}
      </div>

      {uso && (
        <div className="card space-y-4">
          <h2 className="font-titulo font-semibold flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-accent" />
            Uso do Mes
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-texto-muted text-xs">Tier</p>
              <div className="flex items-center gap-2 mt-1">
                {uso.tier === "enterprise" ? (
                  <Crown className="w-4 h-4 text-purple-400" />
                ) : uso.tier === "pro" ? (
                  <Zap className="w-4 h-4 text-accent" />
                ) : (
                  <Shield className="w-4 h-4 text-texto-muted" />
                )}
                <span className="text-sm font-medium capitalize">
                  {uso.tier}
                </span>
              </div>
            </div>
            <div>
              <p className="text-texto-muted text-xs">Email</p>
              <p className="text-sm mt-1">{uso.email}</p>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-texto-muted">Requisicoes este mes</span>
              <span className="text-texto-secundario font-mono">
                {uso.requisicoes_mes}
                {limiteUso ? ` / ${limiteUso}` : " / ilimitado"}
              </span>
            </div>
            {limiteUso && limiteUso > 0 && (
              <div className="w-full bg-borda rounded-full h-2">
                <div
                  className="h-2 rounded-full transition-all duration-500"
                  style={{
                    width: `${pctUso}%`,
                    backgroundColor:
                      pctUso >= 90
                        ? "#ff2d4a"
                        : pctUso >= 70
                          ? "#f59e0b"
                          : "#6366f1",
                  }}
                />
              </div>
            )}
          </div>

          <div>
            <p className="text-texto-muted text-xs">Conta criada em</p>
            <p className="text-sm mt-0.5">
              {uso.criado_em
                ? new Date(uso.criado_em).toLocaleDateString("pt-BR")
                : "N/A"}
            </p>
          </div>
        </div>
      )}

      {/* Comparison Table */}
      <div className="card space-y-6">
        <h2 className="font-titulo font-semibold flex items-center gap-2">
          <Zap className="w-4 h-4 text-accent" />
          Planos
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-borda">
                <th className="text-left py-3 pr-4 text-texto-muted text-xs uppercase tracking-wider font-normal">
                  Feature
                </th>
                <th className="text-center py-3 px-4 text-texto-muted text-xs uppercase tracking-wider font-normal">
                  Free
                </th>
                <th className="text-center py-3 px-4 text-xs uppercase tracking-wider font-normal text-accent">
                  Pro
                </th>
                <th className="text-center py-3 pl-4 text-xs uppercase tracking-wider font-normal text-purple-400">
                  Enterprise
                </th>
              </tr>
            </thead>
            <tbody>
              {PLAN_FEATURES.map((f) => (
                <tr
                  key={f.label}
                  className="border-b border-borda/50 hover:bg-borda/10"
                >
                  <td className="py-2.5 pr-4 text-texto-secundario">
                    {f.label}
                  </td>
                  <td className="py-2.5 px-4 text-center">
                    <div className="flex justify-center">
                      <FeatureCheck enabled={f.free} />
                    </div>
                  </td>
                  <td className="py-2.5 px-4 text-center">
                    <div className="flex justify-center">
                      <FeatureCheck enabled={f.pro} />
                    </div>
                  </td>
                  <td className="py-2.5 pl-4 text-center">
                    <div className="flex justify-center">
                      <FeatureCheck enabled={f.enterprise} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="grid grid-cols-3 gap-3 pt-2">
          <div className="text-center">
            <p className="font-titulo font-bold text-lg">$0</p>
            <p className="text-texto-muted text-xs">para sempre</p>
          </div>
          <div className="text-center space-y-2">
            <p className="font-titulo font-bold text-lg text-accent">
              $49<span className="text-sm font-normal text-texto-muted">/dev</span>
            </p>
            <p className="text-texto-muted text-xs">por mes</p>
            {uso && uso.tier === "free" && (
              <div className="space-y-1.5">
                <button
                  onClick={() => handleUpgrade("pro", "pro_monthly")}
                  disabled={upgrading}
                  className="btn-primary text-xs w-full"
                >
                  {upgrading ? "Redirecionando..." : "Assinar Mensal"}
                </button>
                <button
                  onClick={() => handleUpgrade("pro", "pro_yearly")}
                  disabled={upgrading}
                  className="btn-ghost text-xs w-full border border-accent/30 text-accent hover:bg-accent/10"
                >
                  Anual (-20%)
                </button>
              </div>
            )}
            {uso && uso.tier === "pro" && (
              <div className="space-y-1.5">
                <p className="text-xs text-accent font-mono">Plano atual</p>
                <button
                  onClick={handleGerenciarAssinatura}
                  disabled={upgrading}
                  className="btn-ghost text-xs w-full border border-borda"
                >
                  Gerenciar Assinatura
                </button>
              </div>
            )}
          </div>
          <div className="text-center space-y-2">
            <p className="font-titulo font-bold text-lg text-purple-400">
              Custom
            </p>
            <p className="text-texto-muted text-xs">sob consulta</p>
            {uso && uso.tier !== "enterprise" && (
              <a
                href="mailto:sales@specter.dev"
                className="btn-ghost mt-2 text-xs w-full border border-borda inline-block text-center py-2"
              >
                Falar com Vendas
              </a>
            )}
            {uso && uso.tier === "enterprise" && (
              <div className="space-y-1.5">
                <p className="text-xs text-purple-400 font-mono">Plano atual</p>
                <button
                  onClick={handleGerenciarAssinatura}
                  disabled={upgrading}
                  className="btn-ghost text-xs w-full border border-borda"
                >
                  Gerenciar Assinatura
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
