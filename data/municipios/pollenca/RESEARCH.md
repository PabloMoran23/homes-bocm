# Pollença — investigación portal ayuntamiento

Municipio: **Pollença** (`pollenca`) — Illes Balears, Mallorca. INE 07042. Boletín: BOIB (2 entradas en cola).

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal (CMS Plugcore) | https://www.ajpollenca.net |
| Web alternativa (Joomla/YOOtheme) | https://pollensa.com |
| Sede electrónica (espublico gestiona) | https://ajpollenca.sedelectronica.es |
| Tablón de anuncios | https://ajpollenca.sedelectronica.es/board |
| Urbanismo | https://www.ajpollenca.net/ca/urbanisme |
| Planeamiento | https://www.ajpollenca.net/ca/urbanisme/planejament-urbanistic |
| Exposición pública | https://www.ajpollenca.net/ca/exposicio-publica |
| Visor IDE (IDELMA) | https://ide.idelma.cat/visormap/Visors/ide/html/visor042.html |
| Trámites obras (sede) | https://ajpollenca.sedelectronica.es/catalog/t/c70f211b-cab4-41cb-b33e-6f0919264ddb |

## Cómo se listan expedientes

### Tablón sede (espublico / Wicket)

HTML estático en `/board` con filas `<tr><td class="class_name">…`. Campos: documento, expediente (`class_folderCode`), procedimiento (`class_folderName` = p. ej. «Actuacions Urbanístiques»), categoría, descripción, fecha (`class_dateFrom` DD/MM/YYYY), enlace `preview-document/{uuid}`.

Ejemplo reciente (ago 2026): aprobación inicial modificación puntual plan parcial sector UP4-A PGOU (exp. 2782/2026), con PDFs en preview-document.

### Visor GIS — expedientes Absis (WFS)

GeoServer IDELMA expone capa **`M042_URBANISME:exp_absis`** («Expedients extrets de la base de dades d'Absis»):

```
GET https://ide.idelma.cat/geoserver/M042_URBANISME/wfs
  ?service=WFS&version=1.1.0&request=GetFeature
  &typeName=M042_URBANISME:exp_absis
  &outputFormat=application/json&srsName=EPSG:4326&maxFeatures=500
```

Campos: `numero_expedient_general`, `numero_expedient_particular`, `descripcio`, `nom_promotor`, `refcat`, geometría `MultiPolygon` en WGS84.

~500 features accesibles (límite servidor); todas con polígono.

### Web CMS (Plugcore)

Secciones urbanismo y exposición pública son SPA Angular (`/api/page/.../runtime-js`); el contenido de planeamiento se publica como entradas de blog/categoría `urbanisme`. No hay API JSON pública estable para listar expedientes; se usan páginas semilla + tablón + WFS.

## Licencias de obra

No hay dataset abierto de licencias concesionadas (tipo Madrid GeoJSON). Fuentes:

1. **WFS exp_absis** — expedientes de obra/comunicación/certificado con geometría (histórico Absis).
2. **Tablón** — anuncios puntuales (pocos; mayoría no es licencia individual).
3. **Sede** — trámites informativos OBRES, certificados urbanísticos, aportación documentación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `M042_URBANISME:exp_absis` — polígonos por expediente Absis (EPSG:4326 vía `srsName`)
  - Visor OpenLayers IDELMA (`config042.js`): capas WMS `M042_URBANISME:Projectes Municipals`, `exp_absis`
  - WFS `M042_URBANISME:Projectes_Municipals_d` listada en capabilities pero **no devuelve features** (schema inexistente en servidor)
- **Estrategia:** descarga WFS exp_absis; match por código expediente; centroide del polígono → `lat`/`lon`
- **Limitaciones:**
  - Capa «Projectes Municipals» del visor sin WFS operativo
  - WFS limitado a 500 features por petición (sin paginación fiable vía startIndex)
  - Tablón y páginas CMS sin geometría embebida
  - Consulta expedientes autenticada en `/expedientes` (sin scrape)

## Limitaciones generales

- Dos dominios web (`ajpollenca.net` corporativo, `pollensa.com` turismo/Joomla).
- Sede espublico estable; SSL OK.
- Exposición pública: contenido editorial, no listado estructurado.
- Email urbanismo: infourbanisme@ajpollenca.net (solo contacto).
