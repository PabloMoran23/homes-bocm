import L from "leaflet";
import type { Feature } from "geojson";
import {
  FOCUS_BOUNDARY_ACCENT,
  FOCUS_BOUNDARY_COLOR,
  FOCUS_MASK_PANE,
  FOCUS_MASK_PANE_Z,
  FOCUS_VEIL_COLOR,
  featurePolygonRings,
  polygonFeaturesOf,
} from "@/lib/map-focus-mask";

type MaskOptions = {
  progress?: number;
};

function ensurePane(map: L.Map) {
  const existing = map.getPane(FOCUS_MASK_PANE);
  if (existing) return existing;
  const pane = map.createPane(FOCUS_MASK_PANE);
  pane.style.zIndex = FOCUS_MASK_PANE_Z;
  pane.style.pointerEvents = "none";
  return pane;
}

function screenPointsOf(map: L.Map, features: Feature[]): Array<{ x: number; y: number }> {
  const pts: Array<{ x: number; y: number }> = [];
  for (const feature of features) {
    for (const polygon of featurePolygonRings(feature)) {
      const outer = polygon[0];
      if (!outer) continue;
      for (const [lat, lng] of outer) {
        const p = map.latLngToContainerPoint([lat, lng]);
        pts.push({ x: p.x, y: p.y });
      }
    }
  }
  return pts;
}

function focusMetrics(
  map: L.Map,
  features: Feature[],
): { cx: number; cy: number; innerR: number; outerR: number } | null {
  const pts = screenPointsOf(map, features);
  if (pts.length === 0) return null;

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of pts) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }

  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const innerR = Math.max(24, Math.hypot(maxX - cx, maxY - cy));
  const outerR = innerR * 1.18 + 20;
  return { cx, cy, innerR, outerR };
}

function addPolygonRings(
  ctx: CanvasRenderingContext2D,
  map: L.Map,
  features: Feature[],
) {
  for (const feature of features) {
    for (const polygon of featurePolygonRings(feature)) {
      for (const ring of polygon) {
        if (ring.length < 3) continue;
        const first = ring[0]!;
        const last = ring[ring.length - 1]!;
        const closed = first[0] === last[0] && first[1] === last[1];
        const end = closed ? ring.length - 1 : ring.length;
        for (let i = 0; i < end; i++) {
          const [lat, lng] = ring[i]!;
          const p = map.latLngToContainerPoint([lat, lng]);
          if (i === 0) ctx.moveTo(p.x, p.y);
          else ctx.lineTo(p.x, p.y);
        }
        ctx.closePath();
      }
    }
  }
}

export class HomesFocusMask extends L.Layer {
  private _canvas: HTMLCanvasElement | null = null;
  private _features: Feature[] = [];
  private _progress = 0;
  private _raf = 0;
  private _animFrom = 0;
  private _animTo = 0;
  private _animStart = 0;
  private _animDuration = 380;
  private _onMove: (() => void) | null = null;

  constructor(options?: MaskOptions) {
    super();
    if (options?.progress != null) this._progress = options.progress;
  }

  setFeatures(features: Feature[] | null | undefined) {
    this._features = polygonFeaturesOf(features);
    this._redraw();
    return this;
  }

  getProgress() {
    return this._progress;
  }

  setProgress(progress: number) {
    this._progress = Math.min(1, Math.max(0, progress));
    this._redraw();
    return this;
  }

  animateProgress(to: number, durationMs = 380) {
    window.cancelAnimationFrame(this._raf);
    this._animFrom = this._progress;
    this._animTo = Math.min(1, Math.max(0, to));
    this._animStart = performance.now();
    this._animDuration = Math.max(1, durationMs);
    const tick = (now: number) => {
      const t = Math.min(1, (now - this._animStart) / this._animDuration);
      const eased = 1 - (1 - t) ** 3;
      this.setProgress(this._animFrom + (this._animTo - this._animFrom) * eased);
      if (t < 1) this._raf = window.requestAnimationFrame(tick);
    };
    this._raf = window.requestAnimationFrame(tick);
    return this;
  }

  onAdd(map: L.Map) {
    ensurePane(map);
    const canvas = L.DomUtil.create("canvas", "homes-focus-mask-canvas", map.getPane(FOCUS_MASK_PANE));
    canvas.style.pointerEvents = "none";
    canvas.style.background = "transparent";
    this._canvas = canvas;
    this._onMove = () => this._redraw();
    map.on("move zoom zoomend viewreset resize", this._onMove);
    this._redraw();
    return this;
  }

  onRemove(map: L.Map) {
    window.cancelAnimationFrame(this._raf);
    if (this._onMove) {
      map.off("move zoom zoomend viewreset resize", this._onMove);
      this._onMove = null;
    }
    if (this._canvas?.parentNode) {
      this._canvas.parentNode.removeChild(this._canvas);
    }
    this._canvas = null;
    return this;
  }

  private _redraw() {
    const map = this._map;
    const canvas = this._canvas;
    if (!map || !canvas) return;

    const size = map.getSize();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const topLeft = map.containerPointToLayerPoint([0, 0]);
    L.DomUtil.setPosition(canvas, topLeft);

    if (canvas.width !== Math.round(size.x * dpr) || canvas.height !== Math.round(size.y * dpr)) {
      canvas.width = Math.round(size.x * dpr);
      canvas.height = Math.round(size.y * dpr);
      canvas.style.width = `${size.x}px`;
      canvas.style.height = `${size.y}px`;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.x, size.y);

    const progress = this._progress;
    if (progress < 0.01 || this._features.length === 0) return;

    const metrics = focusMetrics(map, this._features);
    if (!metrics) return;

    const { cx, cy, innerR, outerR } = metrics;
    const rgb = FOCUS_VEIL_COLOR;
    const atEdge = 0.5 * progress;
    const atFar = progress;

    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    ctx.fillStyle = `rgba(${rgb}, ${atEdge})`;
    ctx.fillRect(0, 0, size.x, size.y);

    const fade = ctx.createRadialGradient(cx, cy, innerR, cx, cy, Math.max(outerR, innerR + 1));
    fade.addColorStop(0, `rgba(${rgb}, 0)`);
    fade.addColorStop(1, `rgba(${rgb}, ${Math.max(0, atFar - atEdge)})`);
    ctx.fillStyle = fade;
    ctx.fillRect(0, 0, size.x, size.y);

    ctx.save();
    ctx.globalCompositeOperation = "destination-out";
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#000";
    ctx.beginPath();
    addPolygonRings(ctx, map, this._features);
    ctx.fill("evenodd");
    ctx.restore();

    ctx.save();
    ctx.beginPath();
    addPolygonRings(ctx, map, this._features);
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.strokeStyle = FOCUS_BOUNDARY_ACCENT;
    ctx.lineWidth = 2.6;
    ctx.setLineDash([]);
    ctx.globalAlpha = 0.2 * progress;
    ctx.stroke();
    ctx.strokeStyle = FOCUS_BOUNDARY_COLOR;
    ctx.lineWidth = 1.4;
    ctx.setLineDash([7, 5.5]);
    ctx.globalAlpha = 0.78 * progress;
    ctx.stroke();
    ctx.restore();
  }
}
