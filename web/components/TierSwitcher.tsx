"use client";

import { useTier } from "./TierProvider";
import { TIER_LABEL, type TierId } from "@/lib/tiers";

const options: TierId[] = ["free", "particular", "empresa"];

export function TierSwitcher() {
  const { tier, setTier } = useTier();

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="tier-select" className="hidden text-xs text-slate-500 sm:inline">
        Plan
      </label>
      <select
        id="tier-select"
        value={tier}
        onChange={(e) => setTier(e.target.value as TierId)}
        className="max-w-[140px] rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs font-medium text-slate-800 shadow-sm outline-none focus:border-[var(--portal-accent)] focus:ring-1 focus:ring-[var(--portal-accent)] sm:max-w-none"
        title="Simulación de plan (sin pago). En producción iría tras login."
      >
        {options.map((id) => (
          <option key={id} value={id}>
            {TIER_LABEL[id]}
          </option>
        ))}
      </select>
    </div>
  );
}
