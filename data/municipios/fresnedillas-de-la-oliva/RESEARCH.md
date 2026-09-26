# Fresnedillas de la Oliva — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress) | https://www.fresnedillasdelaoliva.es |
| Ayuntamiento / áreas de gobierno | https://www.fresnedillasdelaoliva.es/ayuntamiento/ |
| Transparencia (WP) | https://www.fresnedillasdelaoliva.es/transparencia/ |
| Oficina virtual | https://www.fresnedillasdelaoliva.es/oficina-virtual/ |
| Sede electrónica (espublico gestiona) | https://fresnedillasdelaoliva.sedelectronica.es |
| Tablón de anuncios | https://fresnedillasdelaoliva.sedelectronica.es/board |
| Portal transparencia (sede) | https://fresnedillasdelaoliva.sedelectronica.es/transparency/ |
| Área URBANISMO (citizen-service) | https://fresnedillasdelaoliva.sedelectronica.es/citizen-service/ba9ebb99-227d-4ca4-897c-de1ef7994bb4 |
| Catálogo trámites | https://fresnedillasdelaoliva.sedelectronica.es/dossier |
| Normativa sede | https://fresnedillasdelaoliva.sedelectronica.es/normative |
| Visor SITCM Comunidad de Madrid | https://www.madrid.org/cartografia/sitcm/html/visor.htm |

## Cómo se listan expedientes / proyectos

- **Tablón sede (`/board`)**: HTML Wicket (espublico gestiona). Tabla con columnas `Documento`, `Expediente`, `Procedimiento`, `Categoría`, `Descripción`, `Fecha`. Enlaces `preview-document/{uuid}`. Solo 2 anuncios activos (bandos no urbanísticos) a fecha de investigación.
- **Transparencia sede (`/transparency/`)**: árbol de secciones (p. ej. «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con 6 documentos). Carga parcial vía AJAX Wicket; en HTML inicial aparece al menos un `preview-document`.
- **WordPress**: páginas hijas de `/ayuntamiento/` (actas de pleno 2019–2023) con contenido de urbanismo embebido en VC (mejoras viarias, urbanización calles, certificaciones de obra).
- **WFS SITCM**: 33 ámbitos de planeamiento (`UA-*`, `SAU PEÑA GORDA`) con polígonos en `sitcm:VPLA_V_AMBITO`.

## Cómo se publican licencias

- **No hay listado público de licencias concedidas** (ni dataset ni tablón con licencias de obra).
- Trámites informativos en sede: `/dossier` (catálogo) y citizen-service URBANISMO.
- El adapter devuelve páginas de trámite (sede + tablón) como filas informativas de `licencias.jsonl`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDEM Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='FRESNEDILLAS DE LA OLIVA'`
  - Campo ámbito: `DS_NOMB_AMB` (UA-1, UA-2, …, SAU PEÑA GORDA)
  - Visor web: SITCM Madrid (`municipio=056` en catálogo CM)
- **Estrategia:** descargar polígonos vía WFS (`outputFormat=application/json`, `srsName=EPSG:4326`); enriquecer proyectos SITCM con `geom_geojson`; intentar match por código UA/SAU en títulos de plenos/tablon.
- **Limitaciones:**
  - Geometría a nivel de **ámbito de planeamiento**, no de expediente/licencia individual.
  - Tablón sin licencias georreferenciadas.
  - Transparencia con navegación AJAX (no todos los PDFs accesibles sin sesión Wicket).
  - Sin visor urbanístico propio del ayuntamiento.

## Limitaciones generales

- Portal WP sin sección dedicada `/urbanismo/` (404).
- Tablón muy escaso (2 bandos no urbanísticos).
- `/dossier` responde lento (>50 s) — el adapter no depende de él para proyectos.
- Sin datos abiertos de licencias en CSV/GeoJSON.
- SSL válido en sede y web.
