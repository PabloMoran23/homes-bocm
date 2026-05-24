"use client";

import { memo, useCallback } from "react";
import {
  allSigmaClassificationEnabled,
  SIGMA_CLASSIFICATION_AXIS_ORDER,
  type SigmaClassificationAxisId,
  type SigmaClassificationAxisMeta,
  type SigmaClassificationFilters,
} from "@/lib/sigma-classification-filters";

const AxisFieldset = memo(function AxisFieldset({
  axisId,
  label,
  defaultOpen,
  options,
  enabled,
  onToggle,
  onSelectAll,
  onClearAll,
}: {
  axisId: SigmaClassificationAxisId;
  label: string;
  defaultOpen?: boolean;
  options: { value: string; count: number; label: string }[];
  enabled: Set<string>;
  onToggle: (axis: SigmaClassificationAxisId, value: string) => void;
  onSelectAll: (axis: SigmaClassificationAxisId) => void;
  onClearAll: (axis: SigmaClassificationAxisId) => void;
}) {
  const active = enabled.size > 0 && enabled.size < options.length;
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-700">
          {label}
          {active ? (
            <span className="ml-1 font-normal text-slate-400">
              ({enabled.size}/{options.length})
            </span>
          ) : null}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onSelectAll(axisId)}
            className="text-[10px] font-medium text-[var(--portal-accent)] hover:underline"
          >
            Todas
          </button>
          <button
            type="button"
            onClick={() => onClearAll(axisId)}
            className="text-[10px] font-medium text-slate-500 hover:underline"
          >
            Ninguna
          </button>
        </div>
      </div>
      <div className="max-h-32 space-y-1 overflow-y-auto pr-1">
        {options.map((opt) => (
          <label
            key={opt.value}
            className="flex cursor-pointer items-center gap-2 text-xs text-slate-700"
          >
            <input
              type="checkbox"
              className="accent-[var(--portal-accent)]"
              checked={enabled.has(opt.value)}
              onChange={() => onToggle(axisId, opt.value)}
            />
            <span className="leading-snug">
              {opt.label}
              <span className="text-slate-400"> · {opt.count.toLocaleString("es-ES")}</span>
            </span>
          </label>
        ))}
      </div>
    </>
  );

  if (defaultOpen) {
    return <fieldset className="space-y-2">{body}</fieldset>;
  }

  return (
    <details className="rounded-lg border border-slate-100 bg-slate-50/50 px-2 py-1.5">
      <summary className="cursor-pointer text-xs font-semibold text-slate-700">{label}</summary>
      <div className="mt-2 space-y-2 pb-1">{body}</div>
    </details>
  );
});

export const SigmaClassificationFilterPanel = memo(function SigmaClassificationFilterPanel({
  meta,
  filters,
  onChange,
}: {
  meta: SigmaClassificationAxisMeta;
  filters: SigmaClassificationFilters;
  onChange: React.Dispatch<React.SetStateAction<SigmaClassificationFilters | null>>;
}) {
  const toggle = useCallback(
    (axis: SigmaClassificationAxisId, value: string) => {
      onChange((prev) => {
        if (!prev) return prev;
        const next = new Set(prev[axis]);
        if (next.has(value)) next.delete(value);
        else next.add(value);
        return { ...prev, [axis]: next };
      });
    },
    [onChange],
  );

  const selectAll = useCallback(
    (axis: SigmaClassificationAxisId) => {
      onChange((prev) => {
        if (!prev) return prev;
        return { ...prev, [axis]: new Set(meta.options[axis].map((o) => o.value)) };
      });
    },
    [meta.options, onChange],
  );

  const clearAll = useCallback(
    (axis: SigmaClassificationAxisId) => {
      onChange((prev) => {
        if (!prev) return prev;
        return { ...prev, [axis]: new Set() };
      });
    },
    [onChange],
  );

  return (
    <div className="space-y-3 border-t border-slate-100 pt-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Clasificación
        </p>
        <button
          type="button"
          onClick={() => onChange(allSigmaClassificationEnabled(meta))}
          className="text-xs font-medium text-[var(--portal-accent)] hover:underline"
        >
          Reset
        </button>
      </div>
      {SIGMA_CLASSIFICATION_AXIS_ORDER.map((axis) => {
        const options = meta.options[axis.id];
        if (!options.length) return null;
        return (
          <AxisFieldset
            key={axis.id}
            axisId={axis.id}
            label={axis.label}
            defaultOpen={axis.defaultOpen}
            options={options}
            enabled={filters[axis.id]}
            onToggle={toggle}
            onSelectAll={selectAll}
            onClearAll={clearAll}
          />
        );
      })}
    </div>
  );
});
