#!/usr/bin/env node
// Offline-served atlas previews. Network is used only by this explicit generator.
// Source: OpenFreeMap / OpenMapTiles / OpenStreetMap; credits remain in the atlas.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { VectorTile } from '@mapbox/vector-tile';
import { PbfReader } from 'pbf';
import sharp from 'sharp';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = join(root, 'public/maps/provinces');
const directory = JSON.parse(await readFile(join(root, 'data/project-directory.json'), 'utf8'));
const width = 520, height = 260, padding = 35;
const project = ([lng, lat]) => [(lng + 180) / 360, (1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2];
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const inputs = directory.provinces.map(province => ({...province, centers: directory.municipalities.filter(m => m.province === province.slug).map(m => m.center)}));
const signature = input => createHash('sha256').update(JSON.stringify(input)).digest('hex');
if (process.argv.includes('--check')) {
  const manifest = JSON.parse(await readFile(join(output, 'manifest.json'), 'utf8'));
  for (const input of inputs) {
    if (manifest.inputs[input.slug] !== signature(input)) throw new Error(`Regenerate preview: ${input.slug}`);
    const meta = await sharp(join(output, `${input.slug}.webp`)).metadata();
    if (meta.width !== width || meta.height !== height || meta.format !== 'webp') throw new Error(`Invalid preview: ${input.slug}`);
  }
  console.log(`${inputs.length} static province previews verified.`);
  process.exit(0);
}
await mkdir(output, {recursive:true});
const tileJson = await fetch('https://tiles.openfreemap.org/planet').then(r => {if (!r.ok) throw new Error(`TileJSON: ${r.status}`); return r.json();});
const template = tileJson.tiles[0];
const cache = new Map();
async function tile(z, x, y) {
  const url = template.replace('{z}',z).replace('{x}',x).replace('{y}',y);
  if (!cache.has(url)) cache.set(url, (async () => {
    const response = await fetch(url, {signal:AbortSignal.timeout(30000)});
    if (!response.ok) throw new Error(`Tile ${z}/${x}/${y}: ${response.status}`);
    return new VectorTile(new PbfReader(new Uint8Array(await response.arrayBuffer())));
  })());
  return cache.get(url);
}
const manifest = {source: template, width, height, inputs:{}};
for (const input of inputs) {
  if (!input.centers.length) throw new Error(`No centers: ${input.slug}`);
  const points = input.centers.map(project);
  const xs = points.map(p=>p[0]), ys=points.map(p=>p[1]);
  const minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys), maxY=Math.max(...ys);
  const zoom = Math.max(3, Math.min(9, Math.floor(Math.log2(Math.min((width-2*padding)/Math.max(maxX-minX,1e-9),(height-2*padding)/Math.max(maxY-minY,1e-9))/512))));
  const scale=512*2**zoom, left=(minX+maxX)/2*scale-width/2, top=(minY+maxY)/2*scale-height/2;
  const tiles=[];
  for(let x=Math.floor(left/512);x<=Math.floor((left+width)/512);x++) for(let y=Math.floor(top/512);y<=Math.floor((top+height)/512);y++) tiles.push({x,y,data:await tile(zoom,x,y)});
  const paths=[];
  const layers=[['landcover','#dce4cf'],['landuse','#e7e5d7'],['water','#c9dce0'],['waterway','none'],['boundary','none'],['transportation','none']];
  for(const [name,fill] of layers) for(const t of tiles) {
    const layer=t.data.layers[name]; if(!layer) continue;
    for(let i=0;i<layer.length;i++) {
      const f=layer.feature(i), cls=f.properties.class;
      if(name==='transportation' && !['motorway','trunk','primary','secondary'].includes(cls)) continue;
      if(name==='boundary' && Number(f.properties.admin_level)>6) continue;
      const geometry=f.loadGeometry();
      const path=geometry.map(ring=>ring.map((p,j)=>`${j?'L':'M'}${(t.x*512+p.x/layer.extent*512-left).toFixed(1)},${(t.y*512+p.y/layer.extent*512-top).toFixed(1)}`).join('')+(f.type===3?'Z':'')).join('');
      const stroke=name==='transportation'?'#d2b9a8':name==='boundary'?'#acb7a2':name==='waterway'?'#bfd5dd':'none';
      paths.push(`<path d="${path}" fill="${fill}" stroke="${stroke}" stroke-width="${name==='transportation'?1.2:.7}" ${name==='boundary'?'stroke-dasharray="3 3"':''}/>`);
    }
  }
  const labels=[];const occupied=[];
  for(const t of tiles) {
    const layer=t.data.layers.place;if(!layer) continue;
    for(let i=0;i<layer.length;i++) {
      const f=layer.feature(i);if(!['city','town'].includes(f.properties.class)) continue;
      const p=f.loadGeometry()[0][0], x=t.x*512+p.x/layer.extent*512-left, y=t.y*512+p.y/layer.extent*512-top;
      if(x<30||x>width-30||y<15||y>height-15||occupied.some(q=>Math.abs(q[0]-x)<65&&Math.abs(q[1]-y)<20))continue;
      occupied.push([x,y]);labels.push(`<text x="${x}" y="${y}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#68766b" stroke="#f5f2e9" stroke-width="2" paint-order="stroke">${escape(f.properties['name:es']||f.properties.name||'')}</text>`);
    }
  }
  const dots=points.map(([x,y])=>`<circle cx="${(x*scale-left).toFixed(1)}" cy="${(y*scale-top).toFixed(1)}" r="4" fill="#1f4f53" stroke="#faf7ef" stroke-width="1.5"/>`);
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="#f3efe4"/>${paths.join('')}${labels.join('')}${dots.join('')}</svg>`;
  await sharp(Buffer.from(svg)).webp({quality:80}).toFile(join(output,`${input.slug}.webp`));
  manifest.inputs[input.slug]=signature(input);
  console.log(input.slug);
}
await writeFile(join(output,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(`Generated ${inputs.length} static previews.`);
