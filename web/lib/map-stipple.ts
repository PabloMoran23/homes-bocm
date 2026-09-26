import type { AddLayerObject, Map as MaplibreMap } from "maplibre-gl";

const SIZE = 128;

function hash(n: number): number {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

function paintDot(
  data: Uint8ClampedArray,
  size: number,
  cx: number,
  cy: number,
  radius: number,
  rgba: readonly [number, number, number, number],
) {
  const r0 = Math.max(1, Math.ceil(radius));
  for (let y = cy - r0; y <= cy + r0; y++) {
    for (let x = cx - r0; x <= cx + r0; x++) {
      if (x < 0 || y < 0 || x >= size || y >= size) continue;
      const dx = x - cx;
      const dy = y - cy;
      if (dx * dx + dy * dy > radius * radius) continue;
      const i = (y * size + x) * 4;
      const srcA = rgba[3] / 255;
      const dstA = data[i + 3] / 255;
      const outA = srcA + dstA * (1 - srcA);
      if (outA <= 0) continue;
      data[i] = Math.round((rgba[0] * srcA + data[i] * dstA * (1 - srcA)) / outA);
      data[i + 1] = Math.round((rgba[1] * srcA + data[i + 1] * dstA * (1 - srcA)) / outA);
      data[i + 2] = Math.round((rgba[2] * srcA + data[i + 2] * dstA * (1 - srcA)) / outA);
      data[i + 3] = Math.round(outA * 255);
    }
  }
}

function makeStipple(kind: "park" | "wood" | "grass"): ImageData {
  const view = new Uint8ClampedArray(SIZE * SIZE * 4);
  const cell = kind === "wood" ? 11 : kind === "park" ? 15 : 18;
  const colors: Array<readonly [number, number, number, number]> =
    kind === "wood"
      ? [
          [62, 92, 48, 200],
          [90, 122, 64, 170],
          [46, 72, 40, 150],
        ]
      : kind === "park"
        ? [
            [110, 138, 72, 150],
            [88, 118, 62, 130],
            [142, 160, 96, 110],
          ]
        : [
            [148, 168, 104, 100],
            [120, 148, 86, 90],
          ];

  let n = kind === "wood" ? 3 : kind === "park" ? 11 : 23;
  for (let y = 0; y < SIZE; y += cell) {
    for (let x = 0; x < SIZE; x += cell) {
      n += 1;
      const jx = Math.round(x + hash(n) * cell);
      const jy = Math.round(y + hash(n + 17) * cell);
      const color = colors[n % colors.length];
      const radius = kind === "wood" ? 1.6 + hash(n + 3) * 2.2 : 1.2 + hash(n + 5) * 1.8;
      paintDot(view, SIZE, jx % SIZE, jy % SIZE, radius, color);
    }
  }

  return new ImageData(view, SIZE, SIZE);
}

const STIPPLE_LAYERS: Array<{ beforeId: string; layer: AddLayerObject }> = [
  {
    beforeId: "park",
    layer: {
      id: "landcover-grass-stipple",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "landcover",
      filter: ["==", ["get", "class"], "grass"],
      paint: { "fill-pattern": "stipple-grass", "fill-opacity": 0.85 },
    },
  },
  {
    beforeId: "landcover-wood",
    layer: {
      id: "park-stipple",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "park",
      paint: { "fill-pattern": "stipple-park", "fill-opacity": 0.9 },
    },
  },
  {
    beforeId: "landuse-cemetery",
    layer: {
      id: "landcover-wood-stipple",
      type: "fill",
      source: "openmaptiles",
      "source-layer": "landcover",
      filter: ["==", ["get", "class"], "wood"],
      paint: { "fill-pattern": "stipple-wood", "fill-opacity": 0.95 },
    },
  },
];

function kindFromId(id: string): "park" | "wood" | "grass" | null {
  if (id === "stipple-park") return "park";
  if (id === "stipple-wood") return "wood";
  if (id === "stipple-grass") return "grass";
  return null;
}

function ensureImage(gl: MaplibreMap, id: string) {
  if (gl.hasImage(id)) return;
  const kind = kindFromId(id);
  if (!kind) return;
  gl.addImage(id, makeStipple(kind), { pixelRatio: 2 });
}

export function attachMasterplanStipple(gl: MaplibreMap) {
  gl.setMissingStyleImageResolver(async (id) => {
    ensureImage(gl, id);
  });

  const apply = () => {
    ensureImage(gl, "stipple-park");
    ensureImage(gl, "stipple-wood");
    ensureImage(gl, "stipple-grass");
    for (const { beforeId, layer } of STIPPLE_LAYERS) {
      if (gl.getLayer(layer.id)) continue;
      const before = gl.getLayer(beforeId) ? beforeId : undefined;
      gl.addLayer(layer, before);
    }
  };

  if (gl.isStyleLoaded()) apply();
  else gl.once("load", apply);
}
