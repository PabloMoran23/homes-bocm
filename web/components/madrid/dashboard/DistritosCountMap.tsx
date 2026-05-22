"use client";

import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { ChartCard } from "@/components/madrid/dashboard/ChartCard";
import { fmtChart } from "@/lib/dashboard-chart-theme";
import { HOMES_MAP_TILE_URL } from "@/lib/map-tiles";
import { formatDistritoLabel, normDistritoKey } from "@/lib/madrid-distrito";
import { useLeafletMount } from "@/lib/use-leaflet-mount";
import type {
  MadridDashboardCount,
  MadridDashboardDistritoCentroid,
  MadridDashboardDistritoPoint,
} from "@/lib/types";

const MADRID_CENTER: [number, number] = [40.4168, -3.7038];

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

function FitDistritos({ points }: { points: { lat: number; lng: number }[] }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lng] as [number, number]));
    map.fitBounds(bounds.pad(0.12), { padding: [24, 24], maxZoom: 12, animate: false });
  }, [map, points]);
  return null;
}

function resolvePoints(
  items: MadridDashboardCount[],
  mapPoints?: MadridDashboardDistritoPoint[],
  centroids?: Record<string, MadridDashboardDistritoCentroid>,
) {
  const byKey = new Map<string, MadridDashboardDistritoPoint>();
  for (const p of mapPoints ?? []) {
    byKey.set(normDistritoKey(p.name), p);
  }

  return items
    .map((item) => {
      const key = normDistritoKey(item.name);
      const fromMap = byKey.get(key);
      const fromCentroid = centroids?.[key];
      const lat = fromMap?.lat ?? fromCentroid?.lat ?? null;
      const lng = fromMap?.lng ?? fromCentroid?.lng ?? null;
      if (lat == null || lng == null) return null;
      return {
        name: formatDistritoLabel(fromMap?.name ?? fromCentroid?.label ?? item.name),
        count: item.count,
        lat,
        lng,
      };
    })
    .filter((p): p is NonNullable<typeof p> => p != null);
}

function radiusForCount(count: number, max: number) {
  const t = max > 0 ? count / max : 0;
  return 10 + Math.sqrt(t) * 22;
}

export function DistritosCountMap({
  title,
  items,
  mapPoints,
  centroids,
  valueLabel = "licencias",
}: {
  title: string;
  items: MadridDashboardCount[];
  mapPoints?: MadridDashboardDistritoPoint[];
  centroids?: Record<string, MadridDashboardDistritoCentroid>;
  valueLabel?: string;
}) {
  const { ready, mapKey } = useLeafletMount();

  const points = useMemo(
    () => resolvePoints(items, mapPoints, centroids),
    [items, mapPoints, centroids],
  );

  const maxCount = useMemo(() => Math.max(1, ...points.map((p) => p.count)), [points]);

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
      subtitle={`${points.length} distritos en mapa · radio ∝ volumen de ${valueLabel}`}
      height={380}
      className="md:col-span-2"
    >
      {!ready ? (
        <div className="flex h-full items-center justify-center text-sm text-slate-400">Cargando mapa…</div>
      ) : points.length === 0 ? (
        <p className="flex h-full items-center justify-center text-sm text-slate-500">
          Sin coordenadas para ubicar distritos.
        </p>
      ) : (
        <div className="homes-map-shell h-full overflow-hidden rounded-lg border border-teal-100/70 bg-teal-50/40">
          <MapContainer
            key={mapKey}
            center={MADRID_CENTER}
            zoom={11}
            className="h-full w-full"
            scrollWheelZoom={false}
            attributionControl={false}
          >
            <TileLayer url={HOMES_MAP_TILE_URL} />
            <MapSizeFix />
            <FitDistritos points={points} />
            {points.map((p) => {
              const r = radiusForCount(p.count, maxCount);
              return (
                <CircleMarker
                  key={p.name}
                  center={[p.lat, p.lng]}
                  radius={r}
                  pathOptions={{
                    color: "#0f766e",
                    weight: 2,
                    fillColor: "#14b8a6",
                    fillOpacity: 0.55,
                  }}
                >
                  <Tooltip direction="top" offset={[0, -r]} opacity={0.95}>
                    <span className="text-xs font-medium">{p.name}</span>
                    <br />
                    <span className="text-xs tabular-nums">{fmtChart(p.count)} {valueLabel}</span>
                  </Tooltip>
                  <Popup>
                    <p className="font-semibold text-slate-900">{p.name}</p>
                    <p className="mt-1 text-sm tabular-nums text-slate-600">
                      {fmtChart(p.count)} {valueLabel}
                    </p>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>
      )}
    </ChartCard>
  );
}
