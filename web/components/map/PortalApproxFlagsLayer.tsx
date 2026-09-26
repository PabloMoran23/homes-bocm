"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { CmPortalGeoJson, CmPortalProyectoProps } from "@/lib/cm-portal-geo";

const CARD_W = 200;
const CARD_H = 86;
const PAD = 8;
const ACCENT = "#1f4f53";
const INK = "#2a2622";
const PAPER = "#f7f3eb";

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatFecha(raw: string | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec((raw || "").trim());
  if (!m) return raw?.trim() ? raw : "Sin fecha";
  const month = MONTHS[Number(m[2]) - 1];
  if (!month) return raw || "Sin fecha";
  return `${Number(m[3])} ${month} ${m[1]}`;
}

function hashId(id: string): number {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function unit(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function flagHtml(p: CmPortalProyectoProps): string {
  const title = escapeHtml(p.titulo || p.id);
  const fecha = escapeHtml(formatFecha(p.fecha));
  const href = `/proyecto/${encodeURIComponent(p.id)}`;
  return `<div style="position:relative;width:${CARD_W}px;height:${CARD_H}px;font-family:var(--font-geist-sans),ui-sans-serif,system-ui,sans-serif">
    <a href="${href}" style="position:absolute;left:0;right:0;top:0;height:64px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;gap:4px;padding:8px 12px;border-radius:12px;background:${PAPER};border:1px solid #ebe4d6;box-shadow:0 8px 22px rgba(42,38,34,.14);text-decoration:none;color:${INK}">
      <span style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:13px;font-weight:600;line-height:1.25;letter-spacing:-0.01em">${title}</span>
      <span style="font-size:11px;font-weight:500;line-height:1;color:${ACCENT}">${fecha}</span>
    </a>
    <span style="position:absolute;left:50%;top:64px;width:1.5px;height:8px;background:${ACCENT};transform:translateX(-50%)"></span>
    <span style="position:absolute;left:50%;bottom:0;width:9px;height:9px;border-radius:50%;background:${ACCENT};border:2px solid #fff;box-shadow:0 1px 3px rgba(42,38,34,.35);transform:translateX(-50%)"></span>
  </div>`;
}

type Box = { x: number; y: number; w: number; h: number };

function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.w + PAD && a.x + a.w + PAD > b.x && a.y < b.y + b.h + PAD && a.y + a.h + PAD > b.y;
}

function inside(box: Box, width: number, height: number): boolean {
  return box.x >= 12 && box.y >= 56 && box.x + box.w <= width - 12 && box.y + box.h <= height - 16;
}

export function PortalApproxFlagsLayer({
  geojson,
  visible,
}: {
  geojson: CmPortalGeoJson<CmPortalProyectoProps> | null;
  visible: boolean;
}) {
  const map = useMap();

  useEffect(() => {
    if (!visible || !geojson?.features?.length) return;
    const features = geojson.features.filter(
      (f): f is typeof f & { geometry: { type: "Point"; coordinates: [number, number] } } =>
        f.geometry.type === "Point",
    );
    if (!features.length) return;
    const [lng, lat] = features[0].geometry.coordinates;
    if (![lng, lat].every((n) => Number.isFinite(n))) return;
    const center = L.latLng(lat, lng);
    const group = L.layerGroup().addTo(map);
    L.circleMarker(center, {
      radius: 3,
      color: ACCENT,
      weight: 1,
      fillColor: PAPER,
      fillOpacity: 1,
      interactive: false,
    }).addTo(group);

    const markers: L.Marker[] = [];

    const layout = () => {
      for (const marker of markers) group.removeLayer(marker);
      markers.length = 0;

      const size = map.getSize();
      const origin = map.latLngToContainerPoint(center);
      const reach = Math.min(300, Math.max(120, Math.min(size.x, size.y) * 0.34));
      const placed: Box[] = [];
      const golden = Math.PI * (3 - Math.sqrt(5));

      features.forEach((feature, index) => {
        const seed = hashId(feature.properties.id || feature.properties.titulo || "");
        let chosen: { x: number; y: number } | null = null;
        for (let attempt = 0; attempt < 10; attempt++) {
          const slot = (index * 3 + attempt * 7) % features.length;
          const angle = slot * golden + (unit(seed) - 0.5) * 1.15 + attempt * 0.4;
          const radius = 64 + Math.sqrt((slot + 0.5) / features.length) * reach + (unit(seed * 5 + attempt) - 0.5) * 48;
          const x = origin.x + Math.cos(angle) * radius;
          const y = origin.y + Math.sin(angle) * radius;
          const box = { x: x - CARD_W / 2, y: y - CARD_H, w: CARD_W, h: CARD_H };
          if (!inside(box, size.x, size.y)) continue;
          if (placed.some((other) => overlaps(box, other))) continue;
          placed.push(box);
          chosen = { x, y };
          break;
        }
        if (!chosen) return;
        const latlng = map.containerPointToLatLng(L.point(chosen.x, chosen.y));
        const marker = L.marker(latlng, {
          icon: L.divIcon({
            className: "",
            html: flagHtml(feature.properties),
            iconSize: [CARD_W, CARD_H],
            iconAnchor: [CARD_W / 2, CARD_H],
          }),
          zIndexOffset: 600,
        });
        marker.on("add", () => {
          const el = marker.getElement();
          if (el) L.DomEvent.disableClickPropagation(el);
        });
        marker.addTo(group);
        markers.push(marker);
      });
    };

    layout();
    map.on("move", layout);
    map.on("zoom", layout);
    map.on("resize", layout);
    return () => {
      map.off("move", layout);
      map.off("zoom", layout);
      map.off("resize", layout);
      map.removeLayer(group);
    };
  }, [map, visible, geojson]);

  return null;
}
