"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { UbicacionSearchItem } from "@/lib/ubicacion";
import { ubicacionPath } from "@/lib/ubicacion";

const UbicacionesMap = dynamic(
  () => import("./UbicacionesMap").then((m) => ({ default: m.UbicacionesMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[min(70vh,640px)] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
        Cargando mapa…
      </div>
    ),
  },
);

function norm(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

type GeoCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      ndp: string;
      direccion: string | null;
      distrito: string | null;
      barrio: string | null;
      licencias: number;
      sigma: number;
    };
  }>;
};

export function ExploreUbicacionesApp() {
  const router = useRouter();
  const [geojson, setGeojson] = useState<GeoCollection | null>(null);
  const [searchIndex, setSearchIndex] = useState<UbicacionSearchItem[]>([]);
  const [meta, setMeta] = useState<{ inmueblesConCoords?: number } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [highlightNdp, setHighlightNdp] = useState<string | null>(null);
  const [openSuggest, setOpenSuggest] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [mapRes, searchRes, metaRes] = await Promise.all([
          fetch("/data/ubicaciones-map.geojson"),
          fetch("/data/ubicaciones-search.json"),
          fetch("/data/ubicaciones-meta.json"),
        ]);
        if (!mapRes.ok || !searchRes.ok) {
          throw new Error("missing data");
        }
        if (!cancelled) {
          setGeojson((await mapRes.json()) as GeoCollection);
          setSearchIndex((await searchRes.json()) as UbicacionSearchItem[]);
          if (metaRes.ok) setMeta(await metaRes.json());
        }
      } catch {
        if (!cancelled) {
          setErr(
            "No hay datos de ubicaciones. Ejecuta: python3 db/ingest_madrid_ubicacion.py && python3 db/export_ubicaciones_web.py",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const suggestions = useMemo(() => {
    const nq = norm(q.trim());
    if (nq.length < 2) return [];
    return searchIndex
      .filter((item) => {
        const blob = norm(
          [item.label, item.direccion, item.distrito, item.barrio, item.ndp].join(" "),
        );
        return blob.includes(nq);
      })
      .slice(0, 12);
  }, [q, searchIndex]);

  const filteredGeo = useMemo(() => {
    if (!geojson) return null;
    const nq = norm(q.trim());
    if (nq.length < 2) return geojson;
    const ndpSet = new Set(
      searchIndex
        .filter((item) =>
          norm([item.label, item.direccion, item.distrito, item.ndp].join(" ")).includes(nq),
        )
        .map((i) => i.ndp),
    );
    return {
      ...geojson,
      features: geojson.features.filter((f) => ndpSet.has(f.properties.ndp)),
    };
  }, [geojson, q, searchIndex]);

  const pickSuggestion = useCallback((item: UbicacionSearchItem) => {
    setQ(item.label);
    setHighlightNdp(item.ndp);
    setOpenSuggest(false);
  }, []);

  const goToUbicacion = useCallback(
    (ndp: string) => {
      router.push(ubicacionPath(ndp));
    },
    [router],
  );

  if (err) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {err}
      </div>
    );
  }

  if (!geojson || !filteredGeo) {
    return (
      <div className="space-y-3">
        <div className="h-12 max-w-lg animate-pulse rounded-lg bg-slate-200" />
        <div className="min-h-[min(70vh,640px)] animate-pulse rounded-xl bg-slate-200" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="relative z-20 flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="min-w-0 flex-1 space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Buscar dirección o NDP
          </span>
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOpenSuggest(true);
              setHighlightNdp(null);
            }}
            onFocus={() => setOpenSuggest(true)}
            placeholder="Calle, distrito, NDP edificio…"
            className="w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none ring-[var(--portal-accent)]/25 focus:border-[var(--portal-accent)] focus:ring-2"
            autoComplete="off"
          />
        </label>
        {highlightNdp ? (
          <button
            type="button"
            onClick={() => goToUbicacion(highlightNdp)}
            className="shrink-0 rounded-lg bg-[var(--portal-accent)] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--portal-accent-hover)]"
          >
            Ver ficha
          </button>
        ) : null}
      </div>

      {openSuggest && suggestions.length > 0 ? (
        <ul className="relative z-20 -mt-2 max-h-64 overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {suggestions.map((item) => (
            <li key={item.ndp}>
              <button
                type="button"
                className="w-full px-4 py-2.5 text-left text-sm hover:bg-[var(--portal-accent-soft)]"
                onMouseDown={() => pickSuggestion(item)}
              >
                <span className="font-medium text-slate-900">{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <p className="text-sm text-slate-600">
        <span className="font-semibold text-slate-900">
          {filteredGeo.features.length.toLocaleString("es-ES")}
        </span>{" "}
        ubicaciones en mapa
        {meta?.inmueblesConCoords ? (
          <span className="text-slate-500">
            {" "}
            · {meta.inmueblesConCoords.toLocaleString("es-ES")} edificios Madrid (open data)
          </span>
        ) : null}
        . Haz clic en un punto para abrir la{" "}
        <span className="font-medium text-slate-800">ficha de la ubicación</span>.
      </p>

      <UbicacionesMap
        geojson={filteredGeo}
        highlightNdp={highlightNdp}
        onSelectNdp={goToUbicacion}
      />

      <p className="text-center text-xs text-slate-500">
        También puedes ir directo si conoces el NDP:{" "}
        <Link href="/ubicacion/11067033" className="text-[var(--portal-accent)] hover:underline">
          ejemplo
        </Link>
      </p>
    </div>
  );
}
