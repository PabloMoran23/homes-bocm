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
import { useMapVisualContext } from "@/components/map/useMapVisualContext";
import {
  boundsScaleForContainer,
  capZoomForContainer,
  scaledWeight,
} from "@/lib/map-visual-scale";
import { HOMES_MAP_TILE_URL } from "@/lib/map-tiles";
import { licenciaTituloDesdeTipo } from "@/lib/ubicacion-resumen";

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

/** Encuadre y techo de zoom según radio: menos radio → más cercano. */
function boletinFitForRadius(radiusM: number) {
  if (radiusM <= 300) {
    return { boundsScale: 0.9, maxZoom: 18, padding: 24 };
  }
  if (radiusM <= 500) {
    return { boundsScale: 0.96, maxZoom: 17, padding: 30 };
  }
  if (radiusM <= 800) {
    return { boundsScale: 1.02, maxZoom: 16, padding: 34 };
  }
  return { boundsScale: 1.1, maxZoom: 15, padding: 40 };
}

/** Círculo de radio con trazo escalado en pantallas pequeñas. */
function BoletinSearchCircle({
  lat,
  lng,
  radiusM,
}: {
  lat: number;
  lng: number;
  radiusM: number;
}) {
  const visual = useMapVisualContext();
  return (
    <Circle
      center={[lat, lng]}
      radius={radiusM}
      pathOptions={{
        color: "#0f766e",
        fillColor: "#14b8a6",
        fillOpacity: 0.14,
        weight: scaledWeight(2.5, visual),
        dashArray: "8 5",
      }}
    />
  );
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
  const visual = useMapVisualContext();

  useEffect(() => {
    const fit = () => {
      const { boundsScale, maxZoom, padding } = boletinFitForRadius(radiusM);
      const scale = boundsScaleForContainer(
        boundsScale,
        visual.containerWidth,
        visual.containerHeight,
      );
      const cap = capZoomForContainer(
        maxZoom,
        visual.containerWidth,
        visual.containerHeight,
      );
      const dlat = (radiusM / 111_320) * scale;
      const dlng = (radiusM / (111_320 * Math.cos((lat * Math.PI) / 180))) * scale;
      const bounds = L.latLngBounds(
        [lat - dlat, lng - dlng],
        [lat + dlat, lng + dlng],
      );
      map.fitBounds(bounds, {
        paddingTopLeft: [padding, padding],
        paddingBottomRight: [padding, padding],
        maxZoom: cap,
        animate: false,
      });
    };
    fit();
    const t = window.setTimeout(fit, 120);
    return () => window.clearTimeout(t);
  }, [map, lat, lng, radiusM, visual.containerWidth, visual.containerHeight]);

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
  const shellClass = isPanel
    ? "relative h-[min(42vh,340px)] min-h-[220px] w-full overflow-hidden rounded-2xl border border-teal-100/80 bg-teal-50/50 shadow-lg ring-1 ring-teal-900/5 lg:min-h-[420px] lg:h-[min(72vh,680px)]"
    : "relative h-52 w-full overflow-hidden rounded-xl border border-teal-100/80 bg-teal-50/50 sm:h-60";

  return (
    <div className={`homes-map-shell w-full ${className}`}>
      <div className={shellClass}>
        <MapContainer
          key={`${lat.toFixed(5)}-${lng.toFixed(5)}-${radiusM}`}
          center={[lat, lng]}
          zoom={16}
          className="z-0 h-full w-full"
          style={{ height: "100%", minHeight: isPanel ? 220 : 208 }}
          zoomControl={false}
          attributionControl={false}
          scrollWheelZoom={isPanel}
        >
          <TileLayer url={HOMES_MAP_TILE_URL} />
          <MapSizeFix />
          <FitCircleView lat={lat} lng={lng} radiusM={radiusM} />
          <BoletinSearchCircle lat={lat} lng={lng} radiusM={radiusM} />
          <MapMarkers
            centerLat={lat}
            centerLng={lng}
            licencias={licencias}
            expedientesSigma={expedientesSigma}
            markerSize={markerSize}
          />
          {isPanel ? <ZoomControl position="topright" /> : null}
        </MapContainer>
      </div>

      {isPanel ? (
        <div className="mt-2 rounded-xl border border-slate-200/80 bg-white/95 px-3 py-2.5 text-[10px] text-slate-600 shadow-sm">
          <p className="mb-2 font-semibold uppercase tracking-wide text-slate-500">Leyenda</p>
          <LicenciaMapLegend layout="grid" />
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

      {!isPanel ? (
        <p className="mt-2 text-[10px] text-slate-500">
          Iconos = tipo de licencia · Σ = planeamiento
        </p>
      ) : null}
    </div>
  );
}
