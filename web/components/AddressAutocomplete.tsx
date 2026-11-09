"use client";

import { useEffect, useId, useRef, useState } from "react";
import { isSpainLocation, type AddressLocation } from "@/lib/address-search";
import type { AddressSuggestion } from "@/lib/cartociudad";

export type AddressAutocompleteProps = {
  value: string;
  onChange: (value: string) => void;
  onSelect: (location: AddressLocation) => void;
  onSubmit?: () => void;
  label?: string;
  className?: string;
};

export function AddressAutocomplete({ value, onChange, onSelect, onSubmit, label = "Buscar dirección", className }: AddressAutocompleteProps) {
  const id = useId();
  const list = useRef<HTMLUListElement>(null);
  const pendingSelection = useRef<AbortController | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [chosen, setChosen] = useState("");
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ query: string; items: AddressSuggestion[]; error?: string }>({ query: "", items: [] });
  const query = value.trim();
  const expanded = open && query.length >= 3 && chosen !== value;
  const items = result.query === query ? result.items : [];
  const searching = expanded && result.query !== query;

  useEffect(() => {
    if (!expanded) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/geocode-address/suggestions?q=${encodeURIComponent(query)}`, { signal: controller.signal });
        const data = await response.json();
        if (!response.ok || !Array.isArray(data)) throw new Error();
        if (!controller.signal.aborted) setResult({ query, items: data });
      } catch {
        if (!controller.signal.aborted) setResult({ query, items: [], error: "No se pudieron cargar las direcciones. Vuelve a intentarlo." });
      }
    }, 350);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [expanded, query]);
  useEffect(() => () => pendingSelection.current?.abort(), []);

  async function choose(item: AddressSuggestion) {
    pendingSelection.current?.abort();
    const controller = new AbortController();
    pendingSelection.current = controller;
    setResolving(true); setError("");
    try {
      const params = new URLSearchParams({ id: item.id, type: item.type });
      const response = await fetch(`/api/geocode-address/resolve?${params}`, { signal: controller.signal });
      const data = await response.json();
      if (!response.ok || !isSpainLocation(data)) throw new Error();
      if (controller.signal.aborted) return;
      setChosen(item.label);
      onSelect({ ...data, label: item.label });
      setOpen(false);
    } catch {
      if (!controller.signal.aborted) setError("No se pudo localizar esa dirección. Vuelve a seleccionarla.");
    } finally {
      if (pendingSelection.current === controller) setResolving(false);
    }
  }

  const status = resolving ? "Localizando dirección…" : searching ? "Buscando direcciones…" : result.error || (!items.length ? "No encontramos esa dirección. Añade el municipio o el número." : `${items.length} direcciones encontradas`);
  return <div className="relative min-w-0" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <label htmlFor={id} className="sr-only">{label}</label>
    <input id={id} name="address" type="text" value={value} maxLength={200}
      role="combobox" aria-autocomplete="list" aria-expanded={expanded}
      aria-controls={expanded ? `${id}-options` : undefined}
      aria-activedescendant={expanded && items[active] ? `${id}-option-${active}` : undefined}
      aria-describedby={`${id}-status`} aria-busy={searching || resolving}
      placeholder="Calle, número y municipio" autoComplete="off" spellCheck={false}
      className={className || "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-[var(--portal-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--portal-accent-soft)]"}
      onChange={event => {
        pendingSelection.current?.abort(); setResolving(false); setError(""); setChosen(""); setActive(-1); setOpen(true);
        onChange(event.target.value);
      }}
      onFocus={() => setOpen(true)}
      onKeyDown={event => {
        if (event.nativeEvent.isComposing) return;
        if (event.key === "Escape") { event.preventDefault(); setOpen(false); pendingSelection.current?.abort(); setResolving(false); }
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault(); setOpen(true);
          if (items.length) {
            const index = active < 0 ? (event.key === "ArrowDown" ? 0 : items.length - 1) : (active + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
            setActive(index);
            list.current?.children[index]?.scrollIntoView({ block: "nearest" });
          }
        }
        if (event.key === "Enter") {
          if (resolving) event.preventDefault();
          else if (expanded && items.length) { event.preventDefault(); void choose(items[Math.min(items.length - 1, Math.max(0, active))]); }
          else if (onSubmit) { event.preventDefault(); setOpen(false); onSubmit(); }
        }
      }} />
    {expanded && <div className="absolute z-40 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
      <ul ref={list} id={`${id}-options`} role="listbox" aria-label="Direcciones de España" className="max-h-72 overflow-y-auto py-1">
        {items.map((item, index) => <li key={`${item.type}:${item.id}`} role="option" id={`${id}-option-${index}`} aria-selected={index === active}
          className={`cursor-pointer px-4 py-3 text-sm ${index === active ? "bg-[#edf2ed]" : "hover:bg-slate-50"}`}
          onMouseDown={event => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => { if (!resolving) void choose(item); }}>
          <span className="block font-medium text-slate-900">{item.label}</span>
          <span className="mt-1 block text-xs text-slate-500">{item.type === "callejero" ? "Calle completa · añade un número para concretar" : [item.postalCode, item.municipality].filter(Boolean).join(" · ")}</span>
        </li>)}
      </ul>
      {(searching || resolving || result.error || !items.length) && <p className="px-4 py-2 text-xs text-slate-500">{status}</p>}
    </div>}
    <p id={`${id}-status`} role="status" className={error ? "mt-2 text-xs text-red-700" : "sr-only"}>{error || (expanded ? status : "")}</p>
  </div>;
}
