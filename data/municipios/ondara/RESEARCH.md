# Ondara — investigación portal ayuntamiento

Municipio: **Ondara** (`ondara`) — Alicante, Comunitat Valenciana. INE `03093`. Boletín: DOGV.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.ondara.org/ |
| Urbanisme (WordPress Divi) | https://www.ondara.org/serveis-municipals/urbanisme-2/ |
| Sede electrónica (espublico gestiona) | https://ondara.sedelectronica.es/ |
| Tablón de anuncios | https://ondara.sedelectronica.es/board |
| Transparencia urbanismo (enlace web) | https://ondara.sedelectronica.es/transparency/52540845-cbee-4e1c-9a3a-7c66289baf5e/ |
| Portal transparencia (sección 7) | https://ondara.sedelectronica.es/transparency — «7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT (41)» |
| Catálogo trámites | https://ondara.sedelectronica.es/dossier |
| ICV GVA visor | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion |

## Expedientes / planeamiento

- **ICV GVA WFS:** capa `Planeamiento.Zonificacion`, filtro client-side `cod_ine_mun=03093` — 6 instrumentos únicos (NNSS, PP Salinetas, PP La Serreta, SAU/I-2, etc.).
- **Web ondara.org:** página Urbanisme con PDFs estáticos (`PLANOL-ONDARA.pdf`, Pla Sostenibilitat Turística 2024-29). Normativa urbanística referenciada pero descargas embebidas vía widget (sin API REST).
- **Sede transparencia UUID:** tabla HTML espublico con `preview-document/{uuid}`; enlace desde web municipal; contenido mixto (no solo urbanismo).
- **Tablón /board:** tabla Wicket (~10 filas visibles); paginación AJAX Wicket; en la muestra actual sin edictos urbanísticos recientes (subvenciones, pleno, personal).
- **Consulta expedientes:** https://ondara.sedelectronica.es/expedientes — requiere identificación.

## Licencias

- No hay dataset público de licencias concedidas con coordenadas.
- El ayuntamiento publica obligatoriedad de cartel acreditativo de licencia en obras (noticia 2024); sin registro scrapeable.
- Trámites de obra vía sede (`/dossier`); catálogo Wicket, a menudo lento desde CI.
- Adapter incluye páginas informativas: tablón, dossier y página Urbanisme.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `Planeamiento.Zonificacion`, `cod_ine_mun=03093` (~14 polígonos, 6 instrumentos). Salida GML3 → GeoJSON WGS84. CQL server-side no fiable; filtro client-side en bulk GetFeature.
  - Visor GVA: capa zonificación Comunitat Valenciana (sin enlace directo expediente municipal).
  - Sin geoportal municipal propio ni ArcGIS REST municipal.
- **Estrategia:** instrumentos ICV como filas base (`icv_wfs`); matching por keywords (Salinetas, Serreta, NNSS, SAU) contra polígonos GVA; enriquecimiento tablón/transparencia cuando el título coincide.
- **Limitaciones:** zonificación agregada por instrumento, no delimitación por expediente de licencia; tablón sin paginación Wicket; dossier/normativa sede con timeouts intermitentes.

## Limitaciones generales

- Sede espublico: SSL válido; `insecure_ssl: true` por consistencia con otros adapters espublico.
- Tablón: solo primera página sin simular Wicket AJAX.
- WordPress WP Rocket: contenido dinámico de normativa no scrapeable sin JS.
- Sin re-parse BOCM/DOGV en este adapter.
