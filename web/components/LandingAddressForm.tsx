"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

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
  const isHero = variant === "hero";

  function goToBoletin(e?: FormEvent) {
    e?.preventDefault();
    const q = address.trim();
    router.push(q ? `/boletin?q=${encodeURIComponent(q)}` : "/boletin");
  }

  return (
    <form
      className={isHero ? "mt-6 space-y-3" : "mt-8 space-y-3"}
      onSubmit={goToBoletin}
    >
      <label className="block">
        <span className="sr-only">Tu dirección en Madrid</span>
        <input
          type="text"
          name="address"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="Ej. Calle Gran Vía 28, Madrid"
          autoComplete="street-address"
          className={
            isHero
              ? "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
              : "w-full rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          }
        />
      </label>
      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          className={
            isHero
              ? "inline-flex flex-1 items-center justify-center rounded-xl bg-[var(--portal-accent)] px-5 py-3 text-sm font-semibold text-white shadow-md shadow-teal-900/10 transition hover:bg-[var(--portal-accent-hover)] sm:flex-none sm:px-6"
              : "inline-flex flex-1 items-center justify-center rounded-xl bg-[var(--portal-accent)] px-5 py-3.5 text-sm font-semibold text-white shadow-md shadow-teal-900/10 transition hover:bg-[var(--portal-accent-hover)] sm:flex-none sm:px-8"
          }
        >
          {submitLabel}
        </button>
        {showSecondaryLink ? (
          <Link
            href="/boletin"
            className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            Abrir sin dirección
          </Link>
        ) : null}
      </div>
    </form>
  );
}
