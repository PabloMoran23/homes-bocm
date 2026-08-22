# Ponferrada — investigación portal ayuntamiento

**Municipio:** Ponferrada (Castilla y León, León)  
**Fecha:** 2026-08-22

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Proxia Ecclesia) | https://www.ponferrada.org | Portal activo; requiere `insecure_ssl` (cadena TLS incompleta en algunos entornos) |
| Obras y urbanismo | https://www.ponferrada.org/es/ponferrada-temas/obras-urbanismo | Hub de planeamiento, trámites y noticias |
| Servicios urbanismo | https://www.ponferrada.org/es/ponferrada-temas/obras-urbanismo/servicios | PGOU, modificaciones, planes parciales, archivo PLAU (paginado `.nodos,X,Y`) |
| Trámites urbanismo | https://www.ponferrada.org/es/ponferrada-temas/obras-urbanismo/tramites | Licencia urbanística, DR obras menores, certificados, etc. |
| Noticias urbanismo | https://www.ponferrada.org/es/ponferrada-temas/obras-urbanismo/noticias-novedades | Novedades de planeamiento y obras |
| Catálogo procedimientos | https://www.ponferrada.org/es/catalogo-procedimientos | PDF control urbanístico (14) y ambiental |
| Sede electrónica (espublico) | https://ponferrada.sedelectronica.es | **No operativa** — responde «Sede Electrónica Indeterminada» |
| Junta CYL info pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=115 | 2 documentos en información pública |
| Junta CYL archivo aprobado | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=115 | 5 documentos aprobados |
| Visor SIUR (IDECyL) | https://idecyl.jcyl.es/siur/index.html?id=24115 | Visor regional de planeamiento |

## Cómo se listan expedientes

- **Web municipal (Proxia):** páginas HTML estáticas con PDFs/ZIPs en rutas `.ficheros/`. Listados paginados con URLs `.nodos,offset,pageSize` en servicios y noticias.
- **Junta CYL PlanPublica:** tablas HTML con `doOpen(docId)` para documentos de planeamiento (PAU, GU, CU).
- **IDECyL WFS:** catálogo regional PLAU CyL con sectores, planes parciales e instrumentos (`c_mun=24115`, `n_mun=Ponferrada`).
- **Sede espublico:** no accesible (dominio sin instancia configurada).
- No hay API JSON ni visor ArcGIS municipal de expedientes individuales.

## Cómo se publican licencias

- No hay dataset histórico abierto de concesiones de licencia (como Madrid datos abiertos).
- Tablón de anuncios sede no disponible.
- Trámites informativos en web: licencia urbanística, DR obras menores/actos constructivos/uso suelo, segregación/parcelación, certificados urbanísticos, veladores.
- Estrategia adapter: páginas informativas de trámites (patrón Pozuelo/Móstoles).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1), `urbanismo:plau_cyl_planes_parciales` (4), `urbanismo:plau_cyl_sectores` (62)
  - Filtro: `n_mun = 'Ponferrada'`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `url_doc_info`
  - Visor SIUR: `https://idecyl.jcyl.es/siur/index.html?id=24115`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas web/PlanPublica por coincidencia de código sector (SSUNC/SUNC) en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría individual.
  - Licencias de obra sin georreferencia pública.
  - Sede espublico inoperativa; tablón no scrapeable.
  - Web municipal con certificado TLS problemático en algunos entornos CI.
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.

## Limitaciones generales

- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 3 entradas en CSV).
- Municipio grande (~65.000 hab.); volumen alto de sectores en IDECyL (62).
- Crawl web puede ser lento por paginación y `request_delay_s`.
