"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import { GroupedBarChart } from "@/components/madrid/dashboard/GroupedBarChart";
import { ShareDonut } from "@/components/madrid/dashboard/ShareDonut";
import { YearEvolutionChart } from "@/components/madrid/dashboard/YearEvolutionChart";
import type { EspanaPresentacion, MadridPresentacion, ProyectoInvestigado } from "@/lib/madrid-presentacion";
import { siteContactMailto } from "@/lib/site-contact";
import { projectPath } from "@/lib/project-display";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";

const DistritosCountMap = dynamic(
  () =>
    import("@/components/madrid/dashboard/DistritosCountMap").then((m) => m.DistritosCountMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[380px] animate-pulse items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-sm text-slate-400">
        Cargando mapa…
      </div>
    ),
  },
);

type Tab = "madrid" | "espana";

function fmt(n: number) {
  const rounded = Math.round(n);
  const sign = rounded < 0 ? "-" : "";
  const digits = Math.abs(rounded).toString();
  return sign + digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function Pedido({ subject, children }: { subject: string; children: string }) {
  return (
    <div className="mt-8 rounded-2xl border border-[var(--portal-accent)]/20 bg-[var(--portal-accent-soft)]/50 px-5 py-4">
      <p className="text-sm leading-relaxed text-slate-700">{children}</p>
      <a
        href={siteContactMailto(subject)}
        className="mt-3 inline-flex text-sm font-semibold text-[var(--portal-accent)] hover:underline"
      >
        Pedir este análisis
      </a>
    </div>
  );
}

export function MadridPresentacion({
  data,
  espana,
  proyectos,
}: {
  data: MadridPresentacion;
  espana: EspanaPresentacion | null;
  proyectos: ProyectoInvestigado[];
}) {
  const [tab, setTab] = useState<Tab>("madrid");
  const years = data.licencias.comparativa.map((row) => String(row.year));

  return (
    <div className="min-h-full bg-[var(--portal-paper)]">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--portal-warm)]">
              Qué se mueve
            </p>
            <h1 className="mt-1 text-4xl font-semibold tracking-tight text-[var(--portal-ink)] sm:text-5xl">
              {tab === "madrid" ? "Madrid ciudad" : "España"}
            </h1>
            <p className="mt-1 text-sm text-slate-500">El panorama de la obra y del planeamiento</p>
          </div>
          <div className="inline-flex rounded-full bg-white p-1 ring-1 ring-[var(--portal-paper-deep)]">
            <TabButton active={tab === "madrid"} onClick={() => setTab("madrid")}>
              Madrid ciudad
            </TabButton>
            <TabButton active={tab === "espana"} onClick={() => setTab("espana")}>
              España
            </TabButton>
          </div>
        </div>

        {tab === "madrid" ? (
          <MadridTab data={data} years={years} proyectos={proyectos} />
        ) : (
          <EspanaTab espana={espana} />
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
        active ? "bg-[var(--portal-ink)] text-[var(--portal-paper)]" : "text-slate-600 hover:text-slate-900"
      }`}
    >
      {children}
    </button>
  );
}

function MadridTab({
  data,
  years,
  proyectos,
}: {
  data: MadridPresentacion;
  years: string[];
  proyectos: ProyectoInvestigado[];
}) {
  const lic = data.licencias;
  const planes = data.planes;
  const comparativa = lic.comparativa;
  const procTotal = lic.procedimiento.reduce((sum, item) => sum + item.count, 0);
  const procLead = lic.procedimiento[0];
  const procShare =
    procLead && procTotal > 0 ? `${Math.round((procLead.count / procTotal) * 100)}%` : "—";
  const abiertaOrden = [
    "Información pública",
    "En tramitación",
    "Aprobación inicial",
    "Aprobación provisional",
  ];
  const abiertas = abiertaOrden
    .map((name) => planes.porFase.find((row) => row.name === name))
    .filter((row): row is (typeof planes.porFase)[number] => Boolean(row));
  const cerradas = planes.porFase.find((row) => row.name === "Aprobación definitiva");
  const enObra = planes.porFase.filter((row) => row.name === "Urbanización" || row.name === "Gestión");
  const cruceMax = Math.max(...data.cruce.map((row) => row.licencias), 1);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-12">
        <article className="flex flex-col justify-between rounded-[1.6rem] bg-[var(--portal-accent)] p-6 text-[var(--portal-paper)] shadow-lg shadow-[var(--portal-accent)]/15 lg:col-span-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/70">2025</p>
          <div>
            <p className="mt-6 text-6xl font-semibold tabular-nums tracking-tight">
              {fmt(lic.cambiosLocal2025)}
            </p>
            <p className="mt-3 text-lg leading-snug">
              cambios de local. Superaron a las reformas de piso.
            </p>
          </div>
          <ul className="mt-8 space-y-2 text-sm text-white/80">
            {comparativa.map((row) => (
              <li key={row.year} className="flex items-center justify-between gap-3">
                <span>{row.year}</span>
                <span className="tabular-nums">
                  {fmt(row.aperturas)} locales · {fmt(row.reformasMenores)} pisos
                </span>
              </li>
            ))}
          </ul>
        </article>

        <div className="lg:col-span-5">
          <DistritosCountMap
            title="Dónde se concentra la obra"
            subtitle="Más oscuro, más obra en el distrito."
            items={lic.porDistrito}
            valueLabel="licencias"
          />
        </div>

        <div className="flex flex-col gap-4 lg:col-span-3">
          <article className="flex flex-1 flex-col justify-between rounded-[1.6rem] bg-[var(--portal-ink)] p-5 text-[var(--portal-paper)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/55">
              Aún abiertos
            </p>
            <p className="mt-4 text-5xl font-semibold tabular-nums">{fmt(planes.abiertos)}</p>
            <p className="mt-2 text-sm leading-snug text-white/75">
              planes sin aprobación definitiva. {fmt(planes.abiertosGranAmbito)} son de gran ámbito.
            </p>
          </article>
          <article className="rounded-[1.6rem] bg-white p-5 ring-1 ring-[var(--portal-paper-deep)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--portal-warm)]">
              Local a vivienda
            </p>
            <div className="mt-3 flex items-end gap-4">
              {comparativa.map((row) => (
                <div key={row.year}>
                  <p className="text-2xl font-semibold tabular-nums text-[var(--portal-ink)]">
                    {fmt(row.localAVivienda)}
                  </p>
                  <p className="text-xs text-slate-500">{row.year}</p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs leading-relaxed text-slate-500">Cada año, menos.</p>
          </article>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <GroupedBarChart
            title="Locales y reformas de piso"
            subtitle="En 2025 el cambio de local adelanta a la reforma de piso."
            categories={years}
            valueLabel="licencias"
            series={[
              { name: "Apertura o cambio de local", data: comparativa.map((r) => r.aperturas) },
              { name: "Obras menores en vivienda", data: comparativa.map((r) => r.reformasMenores) },
            ]}
          />
        </div>
        <article className="rounded-[1.6rem] bg-white p-5 shadow-sm ring-1 ring-slate-900/[0.04] lg:col-span-5">
          <h3 className="text-[15px] font-semibold text-slate-900">Cómo entra la obra</h3>
          <p className="mt-0.5 text-xs text-slate-500">Declaración responsable, licencia y el resto de vías.</p>
          <ShareDonut
            items={lic.procedimiento.slice(0, 5)}
            centerLabel={procShare}
            centerHint={procLead?.name ?? ""}
          />
          <ul className="mt-2 space-y-1.5">
            {lic.procedimiento.slice(0, 4).map((item, index) => (
              <li key={item.name} className="flex items-center justify-between gap-3 text-xs">
                <span className="flex min-w-0 items-center gap-2 text-slate-600">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: ["#1f4f53", "#6b8f54", "#c07f6c", "#d4923a"][index] }}
                  />
                  <span className="truncate">{item.name}</span>
                </span>
                <span className="tabular-nums text-slate-500">{fmt(item.count)}</span>
              </li>
            ))}
          </ul>
        </article>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <YearEvolutionChart
            title="El pulso de la obra"
            subtitle="Mes a mes, de un año al siguiente."
            series={comparativa.map((r) => ({ year: r.year, value: r.total }))}
            seriesByMonth={lic.ritmo}
            granularity="month"
            valueLabel="licencias"
            height={280}
          />
        </div>
        <div className="lg:col-span-5">
          <GroupedBarChart
            title="Cuando se toca el edificio"
            subtitle="Nueva planta, reforma, demolición y primera ocupación."
            categories={years}
            valueLabel="licencias"
            stacked
            series={[
              { name: "Nueva planta o ampliación", data: comparativa.map((r) => r.nuevaPlanta) },
              { name: "Reforma del edificio", data: comparativa.map((r) => r.reforma) },
              { name: "Demolición", data: comparativa.map((r) => r.demolicion) },
              { name: "Listo para ocupar", data: comparativa.map((r) => r.primeraOcupacion) },
            ]}
          />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <MeterList title="Barrios con más cambios de local" hint="2025" items={lic.barriosLocal2025} tone="teal" />
        <MeterList title="Barrios con más reformas de piso" hint="2025" items={lic.barriosReforma2025} tone="warm" />
      </div>
      <p className="px-1 text-sm text-slate-600">
        La misma lectura, calle a calle, está en el{" "}
        <Link href="/boletin" className="font-medium text-[var(--portal-accent)] hover:underline">
          boletín de tu zona
        </Link>
        .
      </p>

      <div className="grid gap-4 lg:grid-cols-12">
        <article className="rounded-[1.6rem] bg-white p-6 ring-1 ring-[var(--portal-paper-deep)] lg:col-span-7">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h3 className="text-[15px] font-semibold text-slate-900">Planes todavía en marcha</h3>
              <p className="mt-0.5 text-xs text-slate-500">
                Del anuncio público a la aprobación. Urbanización y gestión llegan después.
              </p>
            </div>
            {cerradas ? (
              <p className="text-right">
                <span className="block text-2xl font-semibold tabular-nums text-[var(--portal-ink)]">
                  {fmt(cerradas.count)}
                </span>
                <span className="text-[11px] text-slate-500">aprobación definitiva</span>
              </p>
            ) : null}
          </div>
          <ol className="mt-6 flex flex-col gap-0 sm:flex-row sm:items-start">
            {abiertas.map((step, index) => (
              <li key={step.name} className="flex flex-1 items-start gap-3 sm:flex-col sm:gap-2">
                <span className="flex items-center gap-2 sm:w-full">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--portal-accent)] text-xs font-semibold text-white">
                    {index + 1}
                  </span>
                  {index < abiertas.length - 1 ? (
                    <span className="hidden h-px flex-1 bg-[var(--portal-paper-deep)] sm:block" />
                  ) : null}
                </span>
                <span className="pb-4 sm:pb-0 sm:pr-3">
                  <span className="block text-sm font-medium text-slate-800">{step.name}</span>
                  <span className="text-xs tabular-nums text-slate-500">{fmt(step.count)}</span>
                </span>
              </li>
            ))}
          </ol>
          {enObra.length > 0 ? (
            <p className="mt-4 text-xs text-slate-500">
              {enObra.map((row) => `${row.name} ${fmt(row.count)}`).join(" · ")}
            </p>
          ) : null}
        </article>
        <div className="flex flex-col gap-4 lg:col-span-5">
          <SplitBar
            title="Quién lo impulsa"
            hint="Privada, municipal y el resto"
            items={planes.iniciativa.slice(0, 3)}
          />
          <SplitBar
            title="Tamaño del ámbito"
            hint="De la parcela pequeña al gran desarrollo"
            items={planes.superficie.slice(0, 4)}
          />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <YearEvolutionChart
            title="Planes que arrancan"
            subtitle="Cuántos expedientes se incoan cada año."
            series={planes.incoados.map((row) => ({ year: row.year, value: row.count }))}
            valueLabel="planes"
            color="#6d28d9"
            height={280}
          />
        </div>
        <article className="rounded-[1.6rem] bg-white p-5 ring-1 ring-[var(--portal-paper-deep)] lg:col-span-5">
          <h3 className="text-[15px] font-semibold text-slate-900">Quienes más impulsan</h3>
          <p className="mt-0.5 text-xs text-slate-500">Los promotores que más aparecen en el planeamiento.</p>
          <ul className="mt-3 divide-y divide-slate-100">
            {planes.promotores.slice(0, 6).map((row) => (
              <li key={row.name} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="capitalize text-slate-800">{row.name}</span>
                <span className="tabular-nums text-slate-500">{fmt(row.count)}</span>
              </li>
            ))}
          </ul>
        </article>
      </div>

      <article className="rounded-[1.6rem] bg-white p-5 ring-1 ring-[var(--portal-paper-deep)]">
        <h3 className="text-[15px] font-semibold text-slate-900">Obra y planes, en el mismo distrito</h3>
        <p className="mt-0.5 text-xs text-slate-500">
          La obra reciente junto al planeamiento de cada distrito. Un plan puede llevar décadas en marcha.
        </p>
        <ul className="mt-4 space-y-2.5">
          {data.cruce.slice(0, 8).map((row) => (
            <li key={row.name} className="grid grid-cols-[9rem_1fr_auto] items-center gap-3 text-sm">
              <span className="truncate text-slate-700">{row.name}</span>
              <span className="h-2 overflow-hidden rounded-full bg-[var(--portal-paper-deep)]">
                <span
                  className="block h-full rounded-full bg-[var(--portal-accent)]"
                  style={{ width: `${Math.max(6, (row.licencias / cruceMax) * 100)}%` }}
                />
              </span>
              <span className="w-28 text-right text-xs tabular-nums text-slate-500">
                {fmt(row.licencias)} · {fmt(row.planes)} planes
              </span>
            </li>
          ))}
        </ul>
      </article>

      {proyectos.length > 0 ? <ProyectosCapital proyectos={proyectos} /> : null}

      <Pedido subject="Análisis urbanístico en Madrid">
        Una calle, un distrito, un barrio o un tipo de obra. Te montamos el recorte con fechas y los
        planes que cubren la zona.
      </Pedido>
    </div>
  );
}

function MeterList({
  title,
  hint,
  items,
  tone,
}: {
  title: string;
  hint: string;
  items: { name: string; count: number }[];
  tone: "teal" | "warm";
}) {
  const top = items.slice(0, 6);
  const max = Math.max(...top.map((item) => item.count), 1);
  const color = tone === "teal" ? "var(--portal-accent)" : "var(--portal-warm)";
  return (
    <article className="rounded-[1.6rem] bg-white p-5 ring-1 ring-[var(--portal-paper-deep)]">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[15px] font-semibold text-slate-900">{title}</h3>
        <p className="text-xs text-slate-500">{hint}</p>
      </div>
      <ul className="mt-4 space-y-3">
        {top.map((item) => (
          <li key={item.name}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate text-slate-700">{item.name}</span>
              <span className="tabular-nums text-slate-500">{fmt(item.count)}</span>
            </div>
            <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-[var(--portal-paper-deep)]">
              <span
                className="block h-full rounded-full"
                style={{ width: `${Math.max(8, (item.count / max) * 100)}%`, background: color }}
              />
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function SplitBar({
  title,
  hint,
  items,
}: {
  title: string;
  hint: string;
  items: { name: string; count: number }[];
}) {
  const total = items.reduce((sum, item) => sum + item.count, 0) || 1;
  const colors = ["#1f4f53", "#6b8f54", "#c07f6c", "#d4923a"];
  return (
    <article className="rounded-[1.6rem] bg-white p-5 ring-1 ring-[var(--portal-paper-deep)]">
      <h3 className="text-[15px] font-semibold text-slate-900">{title}</h3>
      <p className="mt-0.5 text-xs text-slate-500">{hint}</p>
      <div className="mt-4 flex h-3 overflow-hidden rounded-full">
        {items.map((item, index) => (
          <span
            key={item.name}
            style={{ width: `${(item.count / total) * 100}%`, background: colors[index % colors.length] }}
            title={`${item.name}: ${fmt(item.count)}`}
          />
        ))}
      </div>
      <ul className="mt-3 space-y-1">
        {items.map((item, index) => (
          <li key={item.name} className="flex items-center justify-between gap-3 text-xs">
            <span className="flex min-w-0 items-center gap-2 text-slate-600">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: colors[index % colors.length] }} />
              <span className="truncate">{item.name}</span>
            </span>
            <span className="tabular-nums text-slate-500">{fmt(item.count)}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function proyectoTitulo(card: ProyectoInvestigado): string {
  if (card.nombrePublico) return card.nombrePublico;
  const boletin = /^(madrid\.|plan general|convenio|modificaci|anuncio)/i.test(card.denominacion);
  if (!boletin && card.denominacion.length > 0 && card.denominacion.length <= 72) return card.denominacion;
  const head = card.resumen.split(". ")[0]?.trim() || card.denominacion;
  const cut = head.split(/\s+(?:es|ocupa|se sitúa|se situa|forma parte|transforma|recoge)\s+/i)[0]?.trim();
  const name = cut && cut.length >= 8 ? cut : head;
  return name.length > 78 ? `${name.slice(0, 76).trimEnd()}…` : name;
}

function proyectoHref(id: string): string {
  if (/^\d+\/\d+\/\d+/.test(id)) return sigmaFichaPath(id);
  return projectPath(id);
}

function formatSuperficie(m2: number): string {
  if (m2 >= 10_000) {
    const ha = m2 / 10_000;
    if (ha >= 10) return `${fmt(ha)} ha`;
    const tenths = Math.round(ha * 10);
    const whole = Math.floor(tenths / 10);
    const frac = tenths % 10;
    return frac === 0 ? `${whole} ha` : `${whole},${frac} ha`;
  }
  return `${fmt(m2)} m²`;
}

function promotorCorto(value: string): string {
  const raw = value.split(/[,(—–-]/)[0]?.trim() || value;
  return raw.length > 42 ? `${raw.slice(0, 40)}…` : raw;
}

function ProyectosCapital({ proyectos }: { proyectos: ProyectoInvestigado[] }) {
  const capital = proyectos
    .filter((card) => (card.municipio ?? "").toLowerCase() === "madrid")
    .filter((card) => !/^la actuación documentada/i.test(proyectoTitulo(card)))
    .slice(0, 8);
  const [featured, ...rest] = capital;
  if (!featured) return null;
  return (
    <section>
      <h2 className="px-1 text-lg font-semibold text-[var(--portal-ink)]">
        Proyectos más importantes en la capital
      </h2>
      <p className="mt-1 px-1 text-sm text-slate-500">
        Los grandes desarrollos de la capital, por viviendas.
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-12">
        <ProjectCard card={featured} featured />
        <ul className="grid content-start gap-3 sm:grid-cols-2 lg:col-span-7">
          {rest.map((card) => (
            <li key={card.proyectoId}>
              <ProjectCard card={card} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function ProjectCard({ card, featured = false }: { card: ProyectoInvestigado; featured?: boolean }) {
  const title = proyectoTitulo(card);
  const chips = [
    card.viviendas != null ? `${fmt(Math.round(card.viviendas))} viviendas` : null,
    card.superficieM2 != null ? formatSuperficie(card.superficieM2) : null,
    card.promotor ? promotorCorto(card.promotor) : null,
  ].filter(Boolean);
  return (
    <Link
      href={proyectoHref(card.proyectoId)}
      className={
        featured
          ? "flex h-full flex-col justify-between rounded-[1.6rem] bg-[var(--portal-ink)] p-6 text-[var(--portal-paper)] lg:col-span-5"
          : "flex h-full flex-col rounded-2xl bg-white p-4 ring-1 ring-[var(--portal-paper-deep)] transition hover:ring-[var(--portal-accent)]/40"
      }
    >
      <div>
        <p className={`text-xs font-medium ${featured ? "text-white/55" : "text-slate-500"}`}>Madrid</p>
        {featured && card.viviendas != null ? (
          <p className="mt-4 text-5xl font-semibold tabular-nums tracking-tight">{fmt(Math.round(card.viviendas))}</p>
        ) : null}
        <h3 className={`font-semibold leading-snug ${featured ? "mt-2 text-2xl" : "mt-1 text-sm text-slate-900"}`}>
          {title}
        </h3>
      </div>
      {chips.length > 0 ? (
        <p className={`mt-4 text-xs font-medium ${featured ? "text-white/80" : "text-slate-600"}`}>
          {featured ? chips.filter((chip) => !String(chip).includes("viviendas")).join(" · ") : chips.join(" · ")}
        </p>
      ) : null}
    </Link>
  );
}

function EspanaTab({ espana }: { espana: EspanaPresentacion | null }) {
  if (!espana) {
    return (
      <p className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
        El resumen de boletines no está disponible ahora mismo.
      </p>
    );
  }

  const rango =
    espana.yearMin && espana.yearMax ? `${espana.yearMin}–${espana.yearMax}` : "varios años";
  const maxTerritorio = Math.max(...espana.territorios.map((row) => row.count), 1);
  const maxMunicipio = Math.max(...espana.municipios.map((row) => row.count), 1);
  const instrumentoTotal = espana.instrumentos.reduce((sum, row) => sum + row.count, 0);
  const instrumentoLead = espana.instrumentos[0];
  const instrumentoShare =
    instrumentoLead && instrumentoTotal > 0
      ? `${Math.round((instrumentoLead.count / instrumentoTotal) * 100)}%`
      : "—";
  const anosRecientes = espana.porAno.filter((row) => row.year >= 2022 && row.year <= 2025);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-12">
        <article className="flex flex-col justify-between rounded-[1.6rem] bg-[var(--portal-accent)] p-6 text-[var(--portal-paper)] lg:col-span-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/70">España</p>
            <p className="mt-6 text-6xl font-semibold tabular-nums tracking-tight">{fmt(espana.anuncios)}</p>
            <p className="mt-3 text-lg leading-snug">anuncios de planeamiento en más de una década.</p>
          </div>
          <p className="mt-6 text-sm text-white/75">
            De Madrid a las islas. Planeamiento publicado entre {rango}.
          </p>
        </article>
        <div className="lg:col-span-8">
          <YearEvolutionChart
            title="Una década de planeamiento"
            subtitle="Lo que se publica cada año en los boletines."
            series={espana.porAno.map((row) => ({ year: row.year, value: row.count }))}
            valueLabel="anuncios"
            height={280}
          />
        </div>
      </div>

      {anosRecientes.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-4">
          {anosRecientes.map((row) => (
            <article
              key={row.year}
              className="rounded-[1.4rem] bg-white px-5 py-4 ring-1 ring-[var(--portal-paper-deep)]"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{row.year}</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--portal-ink)]">{fmt(row.count)}</p>
              <p className="mt-1 text-xs text-slate-500">anuncios de planeamiento</p>
            </article>
          ))}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-12">
        <article className="rounded-[1.6rem] bg-white p-5 ring-1 ring-[var(--portal-paper-deep)] lg:col-span-7">
          <h3 className="text-[15px] font-semibold text-slate-900">Dónde se publica más</h3>
          <p className="mt-0.5 text-xs text-slate-500">El planeamiento, comunidad a comunidad.</p>
          <ul className="mt-4 space-y-3">
            {espana.territorios.map((row) => (
              <li key={row.name} className="grid grid-cols-[11rem_1fr_auto] items-center gap-3 text-sm">
                <span className="truncate text-slate-700">{row.name}</span>
                <span className="h-2 overflow-hidden rounded-full bg-[var(--portal-paper-deep)]">
                  <span
                    className="block h-full rounded-full bg-[var(--portal-warm)]"
                    style={{ width: `${Math.max(4, (row.count / maxTerritorio) * 100)}%` }}
                  />
                </span>
                <span className="w-16 text-right tabular-nums text-slate-500">{fmt(row.count)}</span>
              </li>
            ))}
          </ul>
        </article>
        <article className="rounded-[1.6rem] bg-white p-5 ring-1 ring-[var(--portal-paper-deep)] lg:col-span-5">
          <h3 className="text-[15px] font-semibold text-slate-900">Qué se tramita</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Planes especiales, estudios de detalle, modificaciones y el resto de figuras.
          </p>
          <ShareDonut
            items={espana.instrumentos}
            centerLabel={instrumentoShare}
            centerHint={instrumentoLead?.name ?? ""}
          />
          <ul className="mt-2 space-y-1.5">
            {espana.instrumentos.slice(0, 5).map((item, index) => (
              <li key={item.name} className="flex items-center justify-between gap-3 text-xs">
                <span className="flex min-w-0 items-center gap-2 text-slate-600">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: ["#1f4f53", "#6b8f54", "#c07f6c", "#d4923a", "#7a5c58"][index] }}
                  />
                  <span className="truncate">{item.name}</span>
                </span>
                <span className="tabular-nums text-slate-500">{fmt(item.count)}</span>
              </li>
            ))}
          </ul>
        </article>
      </div>

      {espana.municipios.length > 0 ? (
        <article className="rounded-[1.6rem] bg-white p-5 ring-1 ring-[var(--portal-paper-deep)]">
          <h3 className="text-[15px] font-semibold text-slate-900">Ciudades con más planeamiento</h3>
          <p className="mt-0.5 text-xs text-slate-500">Además de Madrid capital.</p>
          <ul className="mt-4 grid gap-x-8 gap-y-2.5 sm:grid-cols-2">
            {espana.municipios.map((row) => (
              <li key={row.name} className="grid grid-cols-[1fr_auto] items-center gap-3 text-sm">
                <span className="min-w-0">
                  <span className="block truncate text-slate-700">{row.name}</span>
                  <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-[var(--portal-paper-deep)]">
                    <span
                      className="block h-full rounded-full bg-[var(--portal-accent)]"
                      style={{ width: `${Math.max(8, (row.count / maxMunicipio) * 100)}%` }}
                    />
                  </span>
                </span>
                <span className="tabular-nums text-slate-500">{fmt(row.count)}</span>
              </li>
            ))}
          </ul>
        </article>
      ) : null}

      <Pedido subject="Análisis urbanístico fuera de Madrid">
        Dinos la ciudad y la pregunta. Te montamos el panorama de esa zona.
      </Pedido>
    </div>
  );
}
