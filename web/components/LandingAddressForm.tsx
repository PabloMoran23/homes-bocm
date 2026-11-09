"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AddressAutocomplete } from "@/components/AddressAutocomplete";
import type { AddressLocation } from "@/lib/address-search";

type LandingAddressFormProps = {
  variant?: "hero" | "section";
  submitLabel?: string;
  showSecondaryLink?: boolean;
};

export function LandingAddressForm({
  variant = "section",
  submitLabel = "Ver actividad en mi calle",
  showSecondaryLink = true,
}: LandingAddressFormProps) {
  const router = useRouter();
  const [address, setAddress] = useState("");
  const [selected, setSelected] = useState<AddressLocation | null>(null);
  const isHero = variant === "hero";

  function goToBoletin(e?: FormEvent) {
    e?.preventDefault();
    if (!selected) return;
    const params = new URLSearchParams({ q: selected.label, lat: String(selected.lat), lng: String(selected.lng) });
    if (selected.municipality) params.set("localidad", selected.municipality);
    router.push(`/boletin/resultados?${params}`);
  }

  return (
    <form
      className={isHero ? "mt-6 space-y-3" : "mt-8 space-y-3"}
      onSubmit={goToBoletin}
    >
      <AddressAutocomplete
        value={address}
        onChange={value => { setAddress(value); setSelected(null); }}
        onSelect={location => { setAddress(location.label); setSelected(location); }}
        className={
          isHero
          ? "w-full rounded-xl border border-[var(--portal-paper-deep)] bg-[var(--portal-paper)] px-4 py-3 text-sm text-[var(--portal-ink)] shadow-sm outline-none transition placeholder:text-[var(--portal-ink)]/40 focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          : "w-full rounded-xl border border-[var(--portal-paper-deep)] bg-[var(--portal-paper)] px-4 py-3.5 text-sm text-[var(--portal-ink)] shadow-sm outline-none transition placeholder:text-[var(--portal-ink)]/40 focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
        }
      />
      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          disabled={!selected}
          className={
            isHero
              ? "inline-flex flex-1 items-center justify-center rounded-xl bg-[var(--portal-accent)] px-5 py-3 text-sm font-semibold text-white shadow-md shadow-[var(--portal-accent)]/15 disabled:cursor-not-allowed disabled:opacity-50 transition hover:bg-[var(--portal-accent-hover)] sm:flex-none sm:px-6"
              : "inline-flex flex-1 items-center justify-center rounded-xl bg-[var(--portal-accent)] px-5 py-3.5 text-sm font-semibold text-white shadow-md shadow-[var(--portal-accent)]/15 disabled:cursor-not-allowed disabled:opacity-50 transition hover:bg-[var(--portal-accent-hover)] sm:flex-none sm:px-8"
          }
        >
          {submitLabel}
        </button>
        {showSecondaryLink ? (
          <Link
            href="/boletin"
            className="inline-flex items-center justify-center rounded-xl border border-[var(--portal-paper-deep)] bg-[var(--portal-paper)] px-5 py-3 text-sm font-semibold text-[var(--portal-ink)]/80 shadow-sm transition hover:bg-[var(--portal-paper-deep)]"
          >
            Abrir sin dirección
          </Link>
        ) : null}
      </div>
    </form>
  );
}
