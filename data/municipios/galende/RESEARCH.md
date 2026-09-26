# Galende — investigación portal ayuntamiento

**Fecha:** 2026-09-26  
**Slug:** `galende`  
**BOCyL regional (referencia):** 3 filas

## Resumen

Galende (Sanabria, Zamora) publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web municipal | https://aytogalende.net | Joomla 4 + Helix Ultimate + SP Page Builder | Sección «Normativa Municipal Urbanismo» con expedientes (PDF, Google Drive, transparencia sede) |
| Sede electrónica | https://galende.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, transparencia, catálogo de trámites |
| Junta CYL / IDECyL | https://servicios.jcyl.es/PlanPublica/ + WFS | Java + GeoServer | Planeamiento documental (cód. municipio 085 en Zamora) y capas WFS |

## URLs base y semillas

- Información pública / urbanismo: https://aytogalende.net/index.php/home/informacion-publica
- Tablón web (jDownloads): https://aytogalende.net/index.php/tablon-de-anuncios
- Sede — tablón: https://galende.sedelectronica.es/board/
- Sede — transparencia: https://galende.sedelectronica.es/transparency
- PlanPublica IP: `searchVPubDocMuniPlai.do?provincia=49&municipio=085`
- PlanPublica aprobado: `searchVPubDocMuniPlau.do?provincia=49&municipio=085`

## Cómo se listan expedientes

### Web Joomla

- Lista HTML (`ui-list`) con enlaces a PDFs locales, carpetas Google Drive y anuncios en sede (`/transparency/{uuid}/`).
- Títulos incluyen código de expediente (`193/2022`, `375/2020`, etc.) y referencias catastrales (polígono/parcela).

### Sede espublico

- Tablón: tabla HTML con `preview-document/{uuid}` (mismo patrón que otros municipios CYL).
- Sin API JSON pública; scrape determinista de HTML.

### Junta CYL

- Índices PlanPublica por municipio; documentación en PDF enlazada desde el buscador.

## Licencias de obra

- No hay registro histórico público de concesiones con coordenadas.
- Trámites informativos en sede (`/dossier`) y tablón (anuncios puntuales si mencionan licencia/obra).
- El adapter devuelve páginas de tablón + dossier como referencia de trámite (patrón Pozuelo/Monfarracinos).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `plau_cyl_planes_parciales`, `plau_cyl_instrumentos_ambito`
  - Filtro: `CQL_FILTER=n_mun='Galende'` → polígonos en EPSG:4326
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; intentar enlazar geometría a anuncios web/tablón por coincidencia de título o token; resto centroide municipal + jitter en geocode.
- **Limitaciones:** sin visor urbanístico municipal propio; expedientes en Google Drive/PDF sin georreferencia; consulta de expedientes en sede requiere identificación.

## Limitaciones generales

- Enlaces PDF en la web a veces usan URLs `chrome-extension://` en el HTML exportado; el adapter normaliza a `aytogalende.net`.
- Tablón sede: ventana limitada de anuncios visibles.
- Licencias sin GIS enlazable.

## Estrategia adapter

1. WFS IDECyL → proyectos con geometría
2. Lista web «Normativa Municipal Urbanismo» → proyectos
3. Tablón sede → proyectos/licencias filtrados por keywords
4. Semillas PlanPublica + transparencia → proyectos de planeamiento
5. Páginas informativas sede → licencias (trámites)
