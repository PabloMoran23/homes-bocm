# Guijuelo — investigación portal ayuntamiento

**Municipio:** Guijuelo (Salamanca, Castilla y León)  
**Código INE:** 37154  
**Fecha:** 2026-09-18  
**BOCYL (referencia):** 1 aviso

## Resumen

Guijuelo publica urbanismo en la **web municipal WordPress** (`guijuelo.es`) con enlace a la
**sede electrónica espublico gestiona** (`guijuelo.sedelectronica.es`). El planeamiento aprobado
está en el archivo PLAI de la Junta de Castilla y León. La geometría de sectores y planes parciales
está disponible en el WFS de IDECyL (63 sectores NUM, 9 planes parciales, 1 instrumento DSU).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web urbanismo | `https://guijuelo.es/urbanismo/` | WordPress | Landing con enlace a sede y transparencia |
| Tablón de anuncios | `https://guijuelo.sedelectronica.es/board` | HTML Wicket | Edictos, enajenaciones parcelas, contratación |
| Transparencia urbanismo | `https://guijuelo.sedelectronica.es/transparency/3db63381-f67e-44fa-89ba-039537fb040a/` | HTML Wicket | 202 docs planeamiento (árbol AJAX) |
| Catálogo trámites | `https://guijuelo.sedelectronica.es/dossier.0` | HTML Wicket | Trámites urbanismo/licencias |
| PLAI archivo | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=154` | HTML | DSU delimitación suelo urbano (1994) |
| IDECyL WFS | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | Sectores UBZ/UBN, planes parciales, instrumentos |
| BOCYL | `bocyl.jcyl.es` | HTML | Ej. expte. 1683/2024 plan especial porcino ibérico |

## Tablón de anuncios (`/board`)

Tabla HTML con enlaces `preview-document/{uuid}` (PDF). Ejemplos vigentes (sep 2026):

- Anuncio enajenación onerosa parcela rústica polígono 513 (urbanismo/parcelas)
- Contratación laboral temporal (filtrado como ruido)

## Trámites urbanismo (catálogo sede)

Trámites scrapeables como páginas informativas de licencias:

- Solicitud de Licencia Urbanística
- Solicitud o Renuncia de una Licencia Urbanística
- Modificación del Planeamiento de Desarrollo
- Solicitud de Aprobación de Planeamiento de Desarrollo

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones con coordenadas.

- Anuncios de licencia en tablón cuando se publican edictos.
- Páginas de trámite del catálogo sede como referencia informativa.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 63 sectores (UBZ-R1…UBN-T7, S3.x, …)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 9 planes parciales
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 instrumento (DSU)
  - Filtro: `CQL_FILTER=n_mun = 'Guijuelo'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer tablón por código de sector en título
- **Limitaciones:** licencias del tablón sin geometría enlazable; no hay visor ArcGIS municipal propio;
  sede requiere `insecure_ssl` (certificado Firmaprofesional); transparencia usa árbol AJAX Wicket (no scrapeado)

## Limitaciones

- Certificado SSL sede: emisor no en CA del sistema; adapter usa `insecure_ssl: true`.
- Wicket: URLs con sufijo `.0`; `/dossier.0` puede tardar >60s sin sesión previa.
- Transparencia (202 docs) requiere navegación AJAX; no implementado en adapter.
- Tablón muestra ~10 anuncios recientes; histórico requiere búsqueda POST Wicket.

## Estrategia adapter

1. Bootstrap sesión en `/board` (cookie `JSESSIONID`).
2. Scrape tabla tablón `/board` + extracto `/info.0`.
3. Catálogo trámites `/dossier.0` filtrado por keywords urbanismo/licencia.
4. WFS IDECyL: sectores + planes parciales + instrumentos con `geom_geojson`.
5. Semillas PLAI Junta CYL (provincia 37, municipio 154) y web/transparencia.
6. IDs estables: `guijuelo-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Sede espublico + SSL + WFS: `alba_de_tormes.py`, `bernuy_de_porreros.py`
- WordPress + sede: patrón similar a municipios CYL con web propia
