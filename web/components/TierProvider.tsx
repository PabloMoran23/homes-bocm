"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  getTierLimits,
  parseTierId,
  TIER_COOKIE_NAME,
  TIER_STORAGE_KEY,
  type TierId,
} from "@/lib/tiers";

type Ctx = {
  tier: TierId;
  setTier: (t: TierId) => void;
  limits: ReturnType<typeof getTierLimits>;
};

const TierContext = createContext<Ctx | null>(null);

function writeTierCookie(tier: TierId) {
  if (typeof document === "undefined") return;
  document.cookie = `${TIER_COOKIE_NAME}=${tier};path=/;max-age=31536000;SameSite=Lax`;
}

function readStoredTier(): TierId {
  try {
    const fromLs = localStorage.getItem(TIER_STORAGE_KEY);
    if (fromLs) return parseTierId(fromLs);
    const m = document.cookie.match(
      new RegExp(`(?:^|; )${TIER_COOKIE_NAME}=([^;]*)`),
    );
    if (m?.[1]) return parseTierId(decodeURIComponent(m[1]));
  } catch {
    /* ignore */
  }
  return "free";
}

export function TierProvider({ children }: { children: React.ReactNode }) {
  const [tier, setTierState] = useState<TierId>("free");

  useEffect(() => {
    queueMicrotask(() => {
      const initial = readStoredTier();
      setTierState(initial);
      writeTierCookie(initial);
    });
  }, []);

  const setTier = useCallback((t: TierId) => {
    const v = parseTierId(t);
    setTierState(v);
    try {
      localStorage.setItem(TIER_STORAGE_KEY, v);
    } catch {
      /* ignore */
    }
    writeTierCookie(v);
  }, []);

  const limits = useMemo(() => getTierLimits(tier), [tier]);
  const value = useMemo(
    () => ({ tier, setTier, limits }),
    [tier, setTier, limits],
  );

  return <TierContext.Provider value={value}>{children}</TierContext.Provider>;
}

export function useTier() {
  const c = useContext(TierContext);
  if (!c) throw new Error("useTier debe usarse dentro de TierProvider");
  return c;
}
