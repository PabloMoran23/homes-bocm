"use client";

import { useEffect, useMemo } from "react";
import { Circle, MapContainer, Marker, Popup, TileLayer, ZoomControl, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { LicenciaMapLegend } from "@/components/map/LicenciaMapLegend";
import type { BoletinEvento } from "@/lib/boletin-area";
import {
  clasificarLicenciaMapa,
  createCentroBusquedaDivIcon,
  createLicenciaDivIcon,
  createSigmaDivIcon,
} from "@/lib/licencia-mapa";
import { licenciaTituloDesdeTipo } from "@/lib/ubicacion-resumen";

const TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

/** Leaflet necesita invalidateSize cuando el contenedor obtiene altura real (grid, sticky, dynamic import). */
function MapSizeFix() {
  const map = useMap();
  useEffect(() => {
    const fit = () => map.invalidateSize({ animate: false });
    fit();
    const t1 = window.setTimeout(fit, 80);
    const t2 = window.setTimeout(fit, 400);
    const parent = map.getContainer().parentElement;
    let ro: ResizeObserver | null = null;
    if (parent && typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => fit());
      ro.observe(parent);
    }
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      ro?.disconnect();
    };
  }, [map]);
  return null;
}

/** Encuadra el mapa en el círculo de búsqueda (zoom cercano al radio). */
function FitCircleView({
  lat,
  lng,
  radiusM,
}: {
  lat: number;
  lng: number;
  radiusM: number;
}) {
  const map = useMap();
  useEffect(() => {
    const dlat = radiusM / 111_320;
    const dlng = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180));
    const bounds = L.latLngBounds(
      [lat - dlat * 1.08, lng - dlng * 1.08],
      [lat + dlat * 1.08, lng + dlng * 1.08],
    );
    const maxZoom = radiusM <= 400 ? 17 : radiusM <= 800 ? 16 : 15;
    map.fitBounds(bounds, { padding: [32, 32], maxZoom, animate: false });
  }, [map, lat, lng, radiusM]);
  return null;
}

function MapMarkers({
  centerLat,
  centerLng,
  licencias,
  expedientesSigma,
  markerSize,
}: {
  centerLat: number;
  centerLng: number;
  licencias: BoletinEvento[];
  expedientesSigma: BoletinEvento[];
  markerSize: "sm" | "md";
}) {
  const licPoints = useMemo(
    () =>
      licencias.filter(
        (e): e is BoletinEvento & { lat: number; lng: number } =>
          e.lat != null && e.lng != null && Number.isFinite(e.lat) && Number.isFinite(e.lng),
      ),
    [licencias],
  );

  const sigmaPoints = useMemo(
    () =>
      expedientesSigma.filter(
        (e): e is BoletinEvento & { lat: number; lng: number } =>
          e.lat != null && e.lng != null && Number.isFinite(e.lat) && Number.isFinite(e.lng),
      ),
    [expedientesSigma],
  );

  return (
    <>
      {licPoints.map((ev, i) => {
        const cat = clasificarLicenciaMapa(ev.titulo);
        return (
          <Marker
            key={`lic-${ev.ndp}-${i}`}
            position={[ev.lat, ev.lng]}
            icon={createLicenciaDivIcon(cat, false, markerSize)}
          >
            <Popup className="homes-map-popup" maxWidth={280}>
              <p className="text-sm font-semibold text-slate-900">
                {licenciaTituloDesdeTipo(ev.titulo)}
              </p>
              {ev.direccion ? <p className="mt-1 text-xs text-slate-600">{ev.direccion}</p> : null}
              {ev.distanciaM != null ? (
                <p className="mt-1 text-xs text-slate-500">{ev.distanciaM} m del punto buscado</p>
              ) : null}
            </Popup>
          </Marker>
        );
      })}
      {sigmaPoints.map((ev, i) => (
        <Marker
          key={`sigma-${ev.expedienteGrupo}-${i}`}
          position={[ev.lat, ev.lng]}
          icon={createSigmaDivIcon(markerSize)}
        >
          <Popup className="homes-map-popup" maxWidth={300}>
            <p className="text-sm font-semibold text-slate-900">{ev.titulo}</p>
            {ev.detalle ? <p className="mt-1 text-xs text-slate-600">{ev.detalle}</p> : null}
          </Popup>
        </Marker>
      ))}
      <Marker position={[centerLat, centerLng]} icon={createCentroBusquedaDivIcon()} zIndexOffset={1000}>
        <Popup>
          <p className="text-sm font-semibold text-slate-900">Tu dirección</p>
        </Popup>
      </Marker>
    </>
  );
}

export function BoletinMiniMap({
  lat,
  lng,
  radiusM,
  licencias = [],
  expedientesSigma = [],
  variant = "panel",
  className = "",
}: {
  lat: number;
  lng: number;
  radiusM: number;
  licencias?: BoletinEvento[];
  expedientesSigma?: BoletinEvento[];
  variant?: "compact" | "panel";
  className?: string;
}) {
  const isPanel = variant === "panel";
  const markerSize = isPanel ? "md" : "sm";
  const panelHeight = "min(72vh, 680px)";

  return (
    <div className={`homes-map-shell w-full ${className}`}>
      <div
        className={
          isPanel
            ? "relative w-full overflow-hidden rounded-2xl border border-slate-200/90 bg-slate-100 shadow-lg ring-1 ring-slate-900/5"
            : "relative h-52 w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-100 sm:h-60"
        }
        style={isPanel ? { height: panelHeight, minHeight: 420 } : undefined}
      >
        <MapContainer
          key={`${lat.toFixed(5)}-${lng.toFixed(5)}-${radiusM}`}
          center={[lat, lng]}
          zoom={16}
          className="z-0 h-full w-full"
          style={{ height: "100%", minHeight: isPanel ? 420 : 208 }}
          zoomControl={false}
          attributionControl={false}
          scrollWheelZoom={isPanel}
        >
          <TileLayer url={TILE_URL} />
          <MapSizeFix />
          <FitCircleView lat={lat} lng={lng} radiusM={radiusM} />
          <Circle
            center={[lat, lng]}
            radius={radiusM}
            pathOptions={{
              color: "#0f766e",
              fillColor: "#14b8a6",
              fillOpacity: 0.14,
              weight: 2.5,
              dashArray: "8 5",
            }}
          />
          <MapMarkers
            centerLat={lat}
            centerLng={lng}
            licencias={licencias}
            expedientesSigma={expedientesSigma}
            markerSize={markerSize}
          />
          {isPanel ? <ZoomControl position="topright" /> : null}
        </MapContainer>

        {isPanel ? (
          <div className="pointer-events-none absolute bottom-3 left-3 z-[1000] max-h-[38%] overflow-y-auto rounded-xl border border-white/90 bg-white/93 px-3 py-2.5 text-[10px] text-slate-600 shadow-md backdrop-blur-sm">
            <p className="mb-1.5 font-semibold uppercase tracking-wide text-slate-500">Leyenda</p>
            <LicenciaMapLegend />
            <p className="mt-2 border-t border-slate-100 pt-2 text-slate-500">
              <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-[#0f766e] ring-1 ring-white" />
              Tu dirección ·{" "}
              <span className="inline-flex items-center gap-0.5">
                <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-sky-500 text-[8px] font-bold text-white">
                  Σ
                </span>
                Planeamiento
              </span>
            </p>
          </div>
        ) : null}
      </div>

      {!isPanel ? (
        <p className="mt-2 text-[10px] text-slate-500">
          Iconos = tipo de licencia · Σ = planeamiento
        </p>
      ) : null}
    </div>
  );
}
