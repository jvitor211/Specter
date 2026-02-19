"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  AlertTriangle,
  CheckCircle,
  Package,
  Clock,
  TrendingUp,
  Loader2,
} from "lucide-react";
import { obterStats, obterHealth, type StatsResponse, type HealthStatus } from "@/lib/api";
import { formatarNumero } from "@/lib/utils";
import { useTier } from "@/lib/tier-context";
import Link from "next/link";

function CardStat({
  titulo,
  valor,
  icon: Icon,
  cor,
  subtitulo,
  loading,
}: {
  titulo: string;
  valor: string | number;
  icon: React.ElementType;
  cor: string;
  subtitulo?: string;
  loading?: boolean;
}) {
  return (
    <div className="card flex items-start justify-between">
      <div>
        <p className="text-texto-muted text-xs uppercase tracking-wider mb-1">
          {titulo}
        </p>
        {loading ? (
          <div className="h-8 w-20 bg-borda/50 rounded animate-pulse" />
        ) : (
          <p className="text-2xl font-titulo font-bold">{valor}</p>
        )}
        {subtitulo && (
          <p className="text-texto-muted text-xs mt-1">{subtitulo}</p>
        )}
      </div>
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center"
        style={{ backgroundColor: `${cor}15` }}
      >
        <Icon className="w-5 h-5" style={{ color: cor }} />
      </div>
    </div>
  );
}

function corVerdict(verdict: string) {
  if (verdict === "blocked") return "text-risco-alto";
  if (verdict === "review") return "text-risco-medio";
  return "text-risco-baixo";
}

function badgeCls(verdict: string) {
  if (verdict === "blocked") return "badge-risco-alto";
  if (verdict === "review") return "badge-risco-medio";
  return "badge-risco-baixo";
}

function traduzir(verdict: string) {
  if (verdict === "blocked") return "Bloqueado";
  if (verdict === "review") return "Revisar";
  return "Seguro";
}

function tempoRelativo(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `${min}min atras`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h atras`;
  return `${Math.floor(h / 24)}d atras`;
}

const tooltipStyle = {
  backgroundColor: "#13151c",
  border: "1px solid #1a1d2e",
  borderRadius: "8px",
  fontSize: "12px",
  color: "#e4e4e7",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const { isFree, restante, limite, pctUso, uso } = useTier();

  useEffect(() => {
    Promise.all([
      obterStats().catch(() => null),
      obterHealth().catch(() => null),
    ]).then(([s, h]) => {
      setStats(s);
      setHealth(h);
      setLoading(false);
    });
  }, []);

  const distribuicao = stats?.distribuicao ?? [];
  const scansDia = stats?.scans_por_dia ?? [];
  const ultimos = stats?.ultimos_scans ?? [];

  return (
    <div className="space-y-8">
      {/* Free tier banner */}
      {uso && isFree && (
        <div
          className={`flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${
            pctUso >= 80
              ? "border-risco-alto/30 bg-risco-alto/5 text-risco-alto"
              : "border-accent/20 bg-accent/5 text-texto-secundario"
          }`}
        >
          <span>
            {pctUso >= 80
              ? `Atencao: ${restante} scans restantes de ${limite} neste mes`
              : `Plano Free — ${restante != null ? `${restante} scans restantes` : "500 scans/mes"}`}
          </span>
          <Link
            href="/settings"
            className="font-mono text-xs uppercase tracking-wider text-accent hover:text-accent/80 transition-colors"
          >
            Upgrade
          </Link>
        </div>
      )}

      {/* Header */}
      <div>
        <h1 className="font-titulo text-2xl font-bold">Dashboard</h1>
        <p className="text-texto-muted text-sm mt-1">
          Visao geral de seguranca do supply chain
        </p>
      </div>

      {/* Cards de Estatisticas */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <CardStat
          titulo="Total Pacotes"
          valor={stats ? formatarNumero(stats.total_pacotes) : "—"}
          icon={Package}
          cor="#ff2d4a"
          subtitulo="No banco"
          loading={loading}
        />
        <CardStat
          titulo="Scans no Mes"
          valor={stats ? formatarNumero(stats.total_scans_mes) : "—"}
          icon={TrendingUp}
          cor="#6366f1"
          subtitulo="Ultimos 30 dias"
          loading={loading}
        />
        <CardStat
          titulo="Sinalizados"
          valor={stats?.total_sinalizados ?? "—"}
          icon={AlertTriangle}
          cor="#f59e0b"
          subtitulo="Review + bloqueados"
          loading={loading}
        />
        <CardStat
          titulo="Taxa de Seguranca"
          valor={stats ? `${stats.taxa_seguranca}%` : "—"}
          icon={CheckCircle}
          cor="#22c55e"
          subtitulo="Pacotes limpos"
          loading={loading}
        />
      </div>

      {/* Graficos */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Line chart — scans por dia */}
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-titulo font-semibold text-sm">
              Scans por Dia
            </h2>
            <div className="flex items-center gap-4 text-xs text-texto-muted">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-accent2" />
                Scans
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-risco-alto" />
                Sinalizados
              </span>
            </div>
          </div>
          {loading ? (
            <div className="h-[260px] flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-texto-muted" />
            </div>
          ) : scansDia.length === 0 ? (
            <div className="h-[260px] flex items-center justify-center text-texto-muted text-sm">
              Nenhum scan registrado ainda
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={scansDia}>
                <CartesianGrid stroke="#1a1d2e" strokeDasharray="3 3" />
                <XAxis
                  dataKey="dia"
                  stroke="#71717a"
                  fontSize={11}
                  tickLine={false}
                />
                <YAxis stroke="#71717a" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  itemStyle={{ color: "#e4e4e7" }}
                  labelStyle={{ color: "#a1a1aa" }}
                />
                <Line
                  type="monotone"
                  dataKey="scans"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="flagged"
                  stroke="#ff2d4a"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Donut — distribuicao de risco */}
        <div className="card">
          <h2 className="font-titulo font-semibold text-sm mb-4">
            Distribuicao de Risco
          </h2>
          {loading ? (
            <div className="h-[200px] flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-texto-muted" />
            </div>
          ) : distribuicao.every((d) => d.value === 0) ? (
            <div className="h-[200px] flex items-center justify-center text-texto-muted text-sm">
              Sem dados de features
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={distribuicao}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {distribuicao.map((entry, i) => (
                    <Cell key={i} fill={entry.cor} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={tooltipStyle}
                  itemStyle={{ color: "#e4e4e7" }}
                  labelStyle={{ color: "#a1a1aa" }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="space-y-2 mt-2">
            {distribuicao.map((item) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: item.cor }}
                  />
                  {item.name}
                </span>
                <span className="font-mono text-texto-secundario">
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tabela — ultimos scans */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-titulo font-semibold text-sm">
            Ultimos Scans
          </h2>
          <span className="text-xs text-texto-muted">
            <Clock className="w-3.5 h-3.5 inline mr-1" />
            Tempo real
          </span>
        </div>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-10 bg-borda/30 rounded animate-pulse" />
            ))}
          </div>
        ) : ultimos.length === 0 ? (
          <p className="text-texto-muted text-sm text-center py-8">
            Nenhum scan realizado ainda. Use a API ou o plugin para escanear pacotes.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-texto-muted text-xs uppercase tracking-wider border-b border-borda">
                  <th className="text-left py-3 pr-4">Pacote</th>
                  <th className="text-left py-3 pr-4">Ecossistema</th>
                  <th className="text-left py-3 pr-4">Score</th>
                  <th className="text-left py-3 pr-4">Veredito</th>
                  <th className="text-right py-3">Quando</th>
                </tr>
              </thead>
              <tbody>
                {ultimos.map((scan, i) => (
                  <tr
                    key={i}
                    className="border-b border-borda/50 hover:bg-borda/20 transition-colors"
                  >
                    <td className="py-3 pr-4 font-mono">{scan.pacote}</td>
                    <td className="py-3 pr-4 text-texto-muted">{scan.ecossistema}</td>
                    <td className="py-3 pr-4">
                      <span className={corVerdict(scan.verdict)}>
                        {scan.score.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <span className={badgeCls(scan.verdict)}>
                        {traduzir(scan.verdict)}
                      </span>
                    </td>
                    <td className="py-3 text-right text-texto-muted text-xs">
                      {tempoRelativo(scan.criado_em)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Status da API */}
      {health && (
        <div className="text-xs text-texto-muted text-right">
          API: {health.status} | Modelo:{" "}
          {health.modelo_carregado ? "Carregado" : "Nao carregado"} | v
          {health.versao_api}
        </div>
      )}
    </div>
  );
}
