# Albalat dels Sorells — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web corporativa | http://www.albalatdelssorells.net |
| API Digital Value | https://api.digitalvalue.es/albalatdelssorells/collections/articulos |
| Área urbanismo (API) | https://api.digitalvalue.es/albalatdelssorells/collections/articulos/634910c75b0e98017f2d0a41 |
| PGOU / modificaciones | https://cdn.digitalvalue.es/albalatdelssorells/pages/es/articulos/62f22ad746a3e0183fc8fcb7 |
| Sede electrónica | https://albalatdelssorells.sedelectronica.es |
| Tablón de anuncios | https://albalatdelssorells.sedelectronica.es/board |
| Catálogo trámites | https://albalatdelssorells.sedelectronica.es/dossier |
| Portal transparencia (web) | http://www.albalatdelssorells.net/es (sección Transparencia) |

## CMS y listado de expedientes

- **Web:** Digital Value / ZityBuilder. ~91 artículos en colección `articulos`. La web pública (`albalatdelssorells.net`) devuelve 502 Bad Gateway desde el entorno del agente; la API REST y CDN (`cdn.digitalvalue.es`) funcionan.
- **Proyectos:** páginas de transparencia/urbanismo en API (`plan-general-de-ordenacion-urbana`, `modificaciones-aprobadas-del-pgou`, `normativa-municipal`, `obras-en-curso`). El PGOU incluye `nodesGroup` con subpáginas de modificaciones.
- **Tablón:** sede espublico gestiona (Wicket). ~9 filas visibles; 2 urbanísticas (exp. 300/2017 Actuació Urbanística).
- **Licencias:** sin registro público de concesiones. Catálogo sede con 6 trámites de urbanismo (DR/comunicación, licencia, actuación urbanística, certificado/informe, recepción obras, modificación licencia).

## Licencias de obra

- Trámites visibles en `/dossier` (UUID en `/catalog/t/...`).
- Consulta de expedientes en `/expedientes` requiere identificación con certificado digital.
- El adapter devuelve fichas informativas de trámites + edictos del tablón filtrados.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` — `https://terramapas.icv.gva.es/0702_Planeamiento`
  - ICV WFS `Planeamiento.Zonificacion` (misma base)
  - Filtro: `CQL_FILTER=COD_INE_MUN='46009'`
  - Formato: GML3, `srsName=EPSG:4326`, paginación `STARTINDEX`
- **Estrategia:** descargar polígonos ICV como proyectos; enriquecer artículos/tablon por coincidencia de tokens sectoriales.
- **Limitaciones:**
  - No hay visor municipal propio enlazado al expediente
  - Geometría ICV es zonificación/sectores, no delimitación por expediente individual
  - Tablón y trámites sin coords explícitas
  - Web corporativa inaccesible (502); contenido vía API/CDN

## Limitaciones generales

- Sede: presentación de trámites requiere certificado digital
- Tablón mezcla urbanismo con personal y BOP (filtro regex)
- BOCM regional: DOGV (1 entrada histórica en cola)
- INE municipio: 46009 (Horta Nord, Valencia)
