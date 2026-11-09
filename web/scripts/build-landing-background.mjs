#!/usr/bin/env node
// Run explicitly to refresh the decorative Madrid map. No network at runtime.
// Cartography: © OpenStreetMap contributors · © OpenMapTiles, via OpenFreeMap.
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { VectorTile } from '@mapbox/vector-tile';
import { PbfReader } from 'pbf';
import sharp from 'sharp';

const width = 1600, height = 900, zoom = 12, tileSize = 512;
const [lng, lat] = [-3.695, 40.425];
const world = tileSize * 2 ** zoom;
const left = (lng + 180) / 360 * world - width / 2;
const top = (1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2 * world - height / 2;
async function fetchChecked(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`${response.status}: ${url}`);
  return response;
}
const tileJson = await (await fetchChecked('https://tiles.openfreemap.org/planet')).json();
const template = tileJson.tiles[0];
const requests = [];
for (let x = Math.floor(left / tileSize); x <= Math.floor((left + width) / tileSize); x++) {
  for (let y = Math.floor(top / tileSize); y <= Math.floor((top + height) / tileSize); y++) {
    requests.push((async () => {
      const response = await fetchChecked(template.replace('{z}', zoom).replace('{x}', x).replace('{y}', y));
      return { x, y, data: new VectorTile(new PbfReader(new Uint8Array(await response.arrayBuffer()))) };
    })());
  }
}
const tiles = await Promise.all(requests);
const paths = [];
const layers = ['landcover', 'landuse', 'park', 'water', 'waterway', 'transportation', 'building'];
for (const name of layers) for (const t of tiles) {
  const layer = t.data.layers[name];
  if (!layer) continue;
  const tilePaths = [];
  for (let i = 0; i < layer.length; i++) {
    const feature = layer.feature(i), cls = feature.properties.class;
    if (feature.properties.brunnel === 'tunnel') continue;
    let fill = 'none', stroke = 'none', strokeWidth = 1, opacity = 1;
    if (name === 'landcover') fill = ({ wood: '#7e9a62', grass: '#d4e0b6', farm: '#ddd6b8', sand: '#e8dcc0' })[cls] || '#d4e0b6';
    if (name === 'landuse') { fill = '#ebe4d6'; opacity = .55; }
    if (name === 'park') fill = '#c7d4a8';
    if (name === 'water') fill = '#1f4f53';
    if (name === 'waterway') { stroke = '#2a5c60'; strokeWidth = 1.7; }
    if (name === 'building') { fill = '#fffcf7'; stroke = '#cfc6ba'; strokeWidth = .4; opacity = .4; }
    if (name === 'transportation') {
      if (['motorway', 'trunk', 'primary'].includes(cls)) { stroke = '#d4a090'; strokeWidth = 3; }
      else if (['secondary', 'tertiary'].includes(cls)) { stroke = '#e6c3b4'; strokeWidth = 1.8; }
      else if (['minor', 'service'].includes(cls)) { stroke = '#fbf7f0'; strokeWidth = .8; }
      else if (['rail', 'transit'].includes(cls)) { stroke = '#c8bdb0'; strokeWidth = .5; }
      else continue;
    }
    const d = feature.loadGeometry().map(ring => ring.map((p, j) =>
      `${j ? 'L' : 'M'}${(t.x * tileSize + p.x / layer.extent * tileSize - left).toFixed(1)},${(t.y * tileSize + p.y / layer.extent * tileSize - top).toFixed(1)}`
    ).join('') + (feature.type === 3 ? 'Z' : '')).join('');
    tilePaths.push(`<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}" opacity="${opacity}"/>`);
  }
  // Clip buffered vector features to their own tile to avoid overlap seams.
  const id = `t-${name}-${t.x}-${t.y}`;
  paths.push(`<defs><clipPath id="${id}"><rect x="${t.x * tileSize - left}" y="${t.y * tileSize - top}" width="${tileSize}" height="${tileSize}"/></clipPath></defs><g clip-path="url(#${id})">${tilePaths.join('')}</g>`);
}
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#f3eee4"/>${paths.join('')}</svg>`;
const output = fileURLToPath(new URL('../public/maps/landing-madrid.webp', import.meta.url));
await mkdir(fileURLToPath(new URL('../public/maps/', import.meta.url)), { recursive: true });
// Bake in the decorative blur; the browser only paints a small static image.
const result = await sharp(Buffer.from(svg)).blur(3).modulate({ saturation: .65 }).webp({ quality: 65 }).toFile(output);
console.log(`Landing background: ${width}×${height}, ${(result.size / 1024).toFixed(1)} KiB`);
