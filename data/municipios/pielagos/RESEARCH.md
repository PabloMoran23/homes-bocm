# Piélagos — investigación portal ayuntamiento

**Municipio:** Piélagos (`pielagos`) — Cantabria  
**Fecha:** 2026-11-03

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.pielagos.es | CMS interactivaclic.com |
| Tablón virtual | https://www.pielagos.es/tablon-de-anuncios-virtual | **Fuente principal** — tabla HTML (fecha + descripción + PDF/BOC) |
| PGOU vigente | https://www.pielagos.es/plan-general-de-ordenacion-vigente | Normas y planos PG93 (ZIP/PDF) |
| PGOU revisiones | `/plan-general-de-ordenacion-2023`, `/plan-general-de-ordenacion-2016-exposicion`, … | Documentación histórica de planeamiento |
| Servicios técnicos | https://www.pielagos.es/servicios-tecnicos | Información urbanística, calificación, licencias (presencial) |
| Sede electrónica | https://sede.pielagos.es/ | Redirección emiservicio ASP (registro/trámites) |
| AUCAN (Gob. Cantabria) | https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/pielagos | Archivo regional (timeout frecuente desde cloud) |
| BOC Cantabria | https://boc.cantabria.es | Enlaces directos desde tablón |

## Cómo se listan expedientes

- **Tablón:** filas `<tr>` con columna fecha `DD-MM-YYYY` y celda con uno o más enlaces (`/app/webroot/blobs/kcfinder/files/*.pdf` o BOC).
- **Expedientes:** patrón `Expediente YYYY/NNNN` o `Expte. YYYY/NNNN` en el texto del anuncio.
- **Planeamiento:** páginas estáticas con enlaces de descarga; no hay visor municipal de expedientes.
- **Sin API JSON** pública de urbanismo.

## Cómo se publican licencias

- **Tablón:** informaciones públicas de solicitud de licencia de actividad (taller, bar, etc.) con dirección y expediente.
- **Servicios técnicos:** trámites presenciales (arquitecto municipal miércoles con cita).
- **Sede:** registro electrónico; no expone histórico scrapeable de concesiones.
- Estrategia adapter: tablón + páginas informativas (PGOU, servicios técnicos, sede).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCAN WFS Cantabria: `https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer`
  - Capa: `Urbanismo:Sectores`
  - Filtro client-side: `Código_INE = 39052` / `Denominación_Municipio = Piélagos`
  - ~24 polígonos (SECTOR 1–9, SUNP-1…12, p. ej. Liencres, Cierro de Sara, Yesera)
  - Visor regional: https://mapas.cantabria.es/
- **Estrategia:** ingestar sectores WFS como proyectos con `geom_geojson`; enriquecer anuncios del tablón si mencionan `Sector N`, `SUNP-N` o topónimos (Liencres, Parbayón, Yesera…).
- **Limitaciones:**
  - Sin visor municipal enlazado a expedientes individuales.
  - Licencias del tablón solo tienen dirección textual.
  - WFS devuelve GML3 (no GeoJSON directo).
  - AUCAN puede no responder desde entornos cloud (no bloqueante).

## Limitaciones generales

- Tablón mezcla urbanismo con padrones de tasas/servicios sociales — filtrados por regex.
- Municipio costero (~25k hab.); volumen alto de filas administrativas en tablón.
- Sede legacy ASP distinta de patrones espublico/OpenSIAC.
- SSL válido en web principal.
