#!/usr/bin/env node
// Simplified IGN boundaries for static atlas thumbnails only (not cadastral use).
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const source = 'https://api-features.ign.es/collections/administrativeunit/items?f=json&limit=100&nationallevelname=Provincia';
const data = process.argv[2] ? JSON.parse(await readFile(process.argv[2], 'utf8')) : await fetch(source, {signal:AbortSignal.timeout(90000)}).then(r=>{if(!r.ok)throw new Error(`IGN: ${r.status}`);return r.json();});
const slug = name => name.split('/')[0].normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,'-');
function distance(p,a,b) {
  const dx=b[0]-a[0],dy=b[1]-a[1];
  const t=dx||dy?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy))):0;
  return (p[0]-a[0]-t*dx)**2+(p[1]-a[1]-t*dy)**2;
}
function simplify(points) {
  const keep=new Set([0,points.length-1]), stack=[[0,points.length-1]];
  while(stack.length) {
    const [start,end]=stack.pop();let best=.002**2,index=-1;
    for(let i=start+1;i<end;i++){const d=distance(points[i],points[start],points[end]);if(d>best){best=d;index=i;}}
    if(index>=0){keep.add(index);stack.push([start,index],[index,end]);}
  }
  const ring=[...keep].sort((a,b)=>a-b).map(i=>points[i]);
  return (ring.length>=4?ring:points).map(p=>p.slice(0,2).map(n=>Number(n.toFixed(5))));
}
const provinces={};
for(const feature of data.features) {
  if(!['Polygon','MultiPolygon'].includes(feature.geometry.type))continue;
  const polygons=feature.geometry.type==='Polygon'?[feature.geometry.coordinates]:feature.geometry.coordinates;
  provinces[slug(feature.properties.nameunit)]={name:feature.properties.nameunit,geometry:{type:'MultiPolygon',coordinates:polygons.map(p=>p.map(simplify))}};
}
await writeFile(fileURLToPath(new URL('../data/province-boundaries.json',import.meta.url)),JSON.stringify({source,attribution:'Límites © IGN',provinces})+'\n');
console.log(`Saved ${Object.keys(provinces).length} IGN province outlines.`);
