"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Package,
  Settings,
  Activity,
} from "lucide-react";
import { SpecterLogo } from "./logo";
import { useTier } from "@/lib/tier-context";

const itensMenu = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/packages", label: "Pacotes", icon: Package },
  { href: "/settings", label: "Configuracoes", icon: Settings },
];

function TierBadge({ tier }: { tier: string }) {
  if (tier === "pro") {
    return (
      <span className="ml-2 px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase tracking-wider bg-accent/15 text-accent border border-accent/30 rounded">
        PRO
      </span>
    );
  }
  if (tier === "enterprise") {
    return (
      <span className="ml-2 px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase tracking-wider bg-purple-500/15 text-purple-400 border border-purple-500/30 rounded">
        ENT
      </span>
    );
  }
  return (
    <span className="ml-2 px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase tracking-wider bg-borda text-texto-muted rounded">
      FREE
    </span>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { tier, isFree, usado, limite, pctUso, loading, uso } = useTier();

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-superficie/80 backdrop-blur-xl border-r border-borda flex flex-col z-50">
      {/* Logo */}
      <div className="p-6 border-b border-borda">
        <Link href="/" className="flex items-center gap-3">
          <SpecterLogo size="md" />
          <div className="flex items-center">
            <h1 className="font-titulo font-bold text-lg tracking-tight">
              Specter
            </h1>
            {!loading && uso && <TierBadge tier={tier} />}
          </div>
        </Link>
      </div>

      {/* Navegacao */}
      <nav className="flex-1 p-4 space-y-1">
        {itensMenu.map(({ href, label, icon: Icon }) => {
          const ativo = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all",
                ativo
                  ? "bg-accent/10 text-accent font-medium"
                  : "text-texto-secundario hover:text-texto-primario hover:bg-borda/30"
              )}
            >
              <Icon className="w-4.5 h-4.5" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Uso + Status */}
      <div className="p-4 border-t border-borda space-y-3">
        {!loading && uso && isFree && limite != null && (
          <div>
            <div className="flex items-center justify-between text-[10px] text-texto-muted mb-1">
              <span>Uso mensal</span>
              <span className="font-mono">{usado} / {limite}</span>
            </div>
            <div className="w-full bg-borda rounded-full h-1.5">
              <div
                className="h-1.5 rounded-full transition-all duration-500"
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
          </div>
        )}
        <div className="flex items-center gap-2 text-xs text-texto-muted">
          <Activity className="w-3.5 h-3.5 text-risco-baixo" />
          <span>API Online</span>
        </div>
        <p className="text-[10px] text-texto-muted">Specter v0.1.0</p>
      </div>
    </aside>
  );
}
