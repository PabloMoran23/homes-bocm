# Ciutadella de Menorca — investigación portal ayuntamiento

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.ajciutadella.org |
| Sede / carpeta ciutadana | https://www.carpetaciutadana.org/ciutadella/portal.aspx |
| Edictes (urbanisme) | https://www.ajciutadella.org/Tauler/edictesX.aspx?TIPO=02 |
| Histórico edictes urbanisme | https://www.ajciutadella.org/Tauler/edictesX.aspx?TIPO=02&HISTORIC=1 |
| Detalle edicto (ej.) | https://www.ajciutadella.org/Tauler/ObrirEdicteExp.aspx?Ig=… |
| Trámites urbanismo | https://www.ajciutadella.org/GesServeis/Tramits.aspx?IDSERVEI=22 |
| PGOU / documentación | https://www.ajciutadella.org/Contingut.aspx?IdPub=2318 |
| PGOU exposición pública (PDFs) | https://www.ajciutadella.org/Contingut.aspx?IdPub=38043 |

Dominio `ciutadella.org` (sin `aj`) está secuestrado; usar solo `ajciutadella.org`.

## Listado de expedientes / planeamiento

- **Tauler d'edictes**: grid ASP.NET DevExpress (`dxgvDataRow`). Columnas: título (enlace a `ObrirEdicteExp.aspx?Ig=<GUID>`), fechas inicio/fin publicación y plazo ciudadano.
- **TIPO=02**: edictes de urbanismo (mezcla de aprobaciones de proyectos, BOIB, consultas previas; también ruido fiscal: IBI, IAE, padrón agua).
- Cada ficha de edicto incluye metadatos (número, fechas, enlace BOIB) y PDFs en `/documents/…`.
- **Planeamiento estático**: páginas `Contingut.aspx` con planimetría PGOU/POD (descarga PDF, sin API).
- **Trámites**: catálogo informativo en `GesServeis/Tramits.aspx` → enlaces `Gestion.aspx?IDGESTION=…` (licencias, DR, certificados). No hay listado público de licencias concedidas con coordenadas.

## Licencias de obra

No hay dataset abierto de licencias otorgadas. El adapter ingiere:

1. Páginas de trámite del catálogo «Urbanisme i Activitats» (comunicación previa, licencias, DR de obras, etc.).
2. Edictos del tauler cuyo título encaja con patrones de licencia/obra (p. ej. reforma clavegueram).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDE Menorca (CIME): WFS `https://ide.cime.es/geoserver/urbanisme/wfs`, capa `urbanisme:or015pod_gestio_zofs` (POD Ciutadella — delimitació àmbits gestió). GeoJSON `EPSG:4326`.
  - Visor insular: https://ide.cime.es (WMS urbanisme); cartografía municipal en PDF (PGOU IdPub 38043).
  - No hay visor municipal con query por código de expediente enlazado al tauler.
- **Estrategia:** tras parsear edictos, extraer tokens del título (p. ej. `UA-32`, nombres de ámbito) y buscar coincidencia en `nomfigura` / `dsfigura` del WFS; adjuntar polígono si hay match.
- **Limitaciones:** proyectos recientes (UA-32, 2026) pueden no estar aún en el WFS; edictos son PDF/HTML sin geometría embebida; licencias sin georef.

## Limitaciones generales

- `/tauler` en `ajciutadella.org` devuelve 403; usar ruta `/Tauler/edictesX.aspx`.
- Carpeta ciutadana replica el tauler pero el scrape usa la web municipal (misma grid).
- Paginación del histórico: parámetro `HISTORIC=1` (~20 filas adicionales en urbanisme).
- Sin RSS del tauler urbanístico identificado.
