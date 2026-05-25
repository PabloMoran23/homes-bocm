"use client";

import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { ChartCard } from "@/components/madrid/dashboard/ChartCard";
import { DistritosGeoLayer } from "@/components/madrid/dashboard/DistritosGeoLayer";
import { FitDistritosBounds } from "@/components/madrid/dashboard/FitDistritosBounds";
import { fmtChart } from "@/lib/dashboard-chart-theme";
import { distritoLegendGradient, distritoQuantileBreaks } from "@/lib/distrito-choropleth";
import { HOMES_MAP_TILE_URL } from "@/lib/map-tiles";
import { normDistritoKey } from "@/lib/madrid-distrito";
import { useLeafletMount } from "@/lib/use-leaflet-mount";
import type {
  MadridDashboardCount,
  MadridDashboardDistritoCentroid,
  MadridDashboardDistritoPoint,
} from "@/lib/types";

const MADRID_DISTRITOS_GEO_URL = "/data/madrid-distritos.geojson";
/** Centro aproximado de Madrid capital (fitBounds lo ajusta al cargar). */
const MADRID_CENTER: [number, number] = [40.42, -3.685];

function MapSizeFix() {
  const map = useMap();
  useEffect(() => {
    const fit = () => map.invalidateSize({ animate: false });
    fit();
    const t = window.setTimeout(fit, 100);
    return () => window.clearTimeout(t);
  }, [map]);
  return null;
}

function buildCountByKey(items: MadridDashboardCount[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const item of items) {
    map.set(normDistritoKey(item.name), item.count);
  }
  return map;
}

export function DistritosCountMap({
  title,
  items,
  valueLabel = "licencias",
}: {
  title: string;
  items: MadridDashboardCount[];
  mapPoints?: MadridDashboardDistritoPoint[];
  centroids?: Record<string, MadridDashboardDistritoCentroid>;
  valueLabel?: string;
}) {
  const { ready, mapKey } = useLeafletMount();
  const [geo, setGeo] = useState<GeoJSON.FeatureCollection | null>(null);
  const [geoError, setGeoError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(MADRID_DISTRITOS_GEO_URL)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((data) => {
        if (!cancelled) setGeo(data as GeoJSON.FeatureCollection);
      })
      .catch(() => {
        if (!cancelled) setGeoError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const countByKey = useMemo(() => buildCountByKey(items), [items]);
  const quantileBreaks = useMemo(
    () => distritoQuantileBreaks(items.map((i) => i.count)),
    [items],
  );

  const matchedCount = useMemo(() => {
    if (!geo?.features?.length) return 0;
    return geo.features.filter((f) => {
      const props = f.properties as { distrito_key?: string } | null;
      return props?.distrito_key && countByKey.has(props.distrito_key);
    }).length;
  }, [geo, countByKey]);

  if (!items.length) {
    return (
      <ChartCard title={title} height={360}>
        <p className="flex h-full items-center justify-center text-sm text-slate-500">Sin datos.</p>
      </ChartCard>
    );
  }

  return (
    <ChartCard
      title={title}
      subtitle={
        geoError
          ? "Límites de distrito no disponibles"
          : `${matchedCount} distritos · color según ${valueLabel}`
      }
      height={380}
    >
      {!ready ? (
        <div className="flex h-full items-center justify-center text-sm text-slate-400">Cargando mapa…</div>
      ) : geoError ? (
        <p className="flex h-full items-center justify-center px-4 text-center text-sm text-slate-500">
          Ejecuta <code className="rounded bg-slate-100 px-1 text-xs">npm run build-data</code> para generar{" "}
          <code className="rounded bg-slate-100 px-1 text-xs">madrid-distritos.geojson</code>.
        </p>
      ) : !geo ? (
        <div className="flex h-full items-center justify-center text-sm text-slate-400">Cargando distritos…</div>
      ) : (
        <div className="flex h-full flex-col gap-2">
          <div className="homes-map-shell min-h-0 flex-1 overflow-hidden rounded-lg border border-teal-100/70 bg-teal-50/40">
            <MapContainer
              key={`${mapKey}-${quantileBreaks.join(",")}`}
              center={MADRID_CENTER}
              zoom={10}
              className="h-full w-full min-h-[280px]"
              scrollWheelZoom={false}
              attributionControl={false}
            >
              <TileLayer url={HOMES_MAP_TILE_URL} />
              <MapSizeFix />
              <FitDistritosBounds geojson={geo} />
              <DistritosGeoLayer
                geojson={geo}
                countByKey={countByKey}
                quantileBreaks={quantileBreaks}
                valueLabel={valueLabel}
              />
            </MapContainer>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-[10px] text-slate-500">
            <span>Menos</span>
            <div
              className="h-2.5 flex-1 max-w-[220px] rounded-full border border-slate-200/80"
              style={{ background: distritoLegendGradient() }}
              aria-hidden
            />
            <span>Más</span>
          </div>
        </div>
      )}
    </ChartCard>
  );
}
