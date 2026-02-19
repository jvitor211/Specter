"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { obterApiKey, obterUso, type UsoAPI } from "./api";

interface TierState {
  uso: UsoAPI | null;
  loading: boolean;
  tier: string;
  isPro: boolean;
  isEnterprise: boolean;
  isFree: boolean;
  usado: number;
  limite: number | null;
  restante: number | null;
  pctUso: number;
  recarregar: () => Promise<void>;
}

const TierContext = createContext<TierState>({
  uso: null,
  loading: true,
  tier: "free",
  isPro: false,
  isEnterprise: false,
  isFree: true,
  usado: 0,
  limite: null,
  restante: null,
  pctUso: 0,
  recarregar: async () => {},
});

export function useTier() {
  return useContext(TierContext);
}

export function TierProvider({ children }: { children: ReactNode }) {
  const [uso, setUso] = useState<UsoAPI | null>(null);
  const [loading, setLoading] = useState(true);

  const recarregar = useCallback(async () => {
    const key = obterApiKey();
    if (!key) {
      setUso(null);
      setLoading(false);
      return;
    }
    try {
      const dados = await obterUso();
      setUso(dados);
    } catch {
      setUso(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  const tier = uso?.tier ?? "free";
  const isPro = tier === "pro";
  const isEnterprise = tier === "enterprise";
  const isFree = tier === "free";
  const usado = uso?.requisicoes_mes ?? 0;
  const limite = uso?.limite_mes ?? null;
  const restante = limite != null ? Math.max(0, limite - usado) : null;
  const pctUso = limite && limite > 0 ? Math.min((usado / limite) * 100, 100) : 0;

  return (
    <TierContext.Provider
      value={{
        uso,
        loading,
        tier,
        isPro,
        isEnterprise,
        isFree,
        usado,
        limite,
        restante,
        pctUso,
        recarregar,
      }}
    >
      {children}
    </TierContext.Provider>
  );
}
