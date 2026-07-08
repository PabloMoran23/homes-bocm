# Sevilla la Nueva — investigación portal ayuntamiento

**Slug:** `sevilla-la-nueva`  
**Nombre oficial:** Sevilla la Nueva  
**Comunidad:** Comunidad de Madrid  
**BOCM (referencia):** 18 anuncios  
**Fecha investigación:** 2026-07-08

## Resumen

Sevilla la Nueva combina web corporativa WordPress (Fortuna/Asdeideas) con sede electrónica **espublico gestiona** (eHome/Wicket). El planeamiento vigente son las **Normas Subsidiarias de 2001** (PDFs en la web) y un **Avance de PGOU** en Dropbox. No hay visor municipal propio; el ayuntamiento enlaza al visor regional de planeamiento de la Comunidad de Madrid.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web — planeamiento | `https://www.sevillalanueva.es/planeamiento/` | WordPress + PDFs | Proyectos (NNSS 2001, modificaciones, planos) |
| Web — avance PGOU | `https://www.sevillalanueva.es/urbanismo/avance-plan-general-de-ordenacion-urbana/` | WordPress + Dropbox | Proyectos (avance PGOU) |
| Web — trámites urbanismo | `https://www.sevillalanueva.es/urbanismo/tramites/` | WordPress informativo | Licencias (páginas trámite) |
| Tablón sede | `https://sevillalanueva.sedelectronica.es/board/` | HTML tabla eHome | Proyectos/licencias vigentes |
| Sede trámites | `https://sevillalanueva.sedelectronica.es/` | eHome (redirect) | Informativo; requiere certificado |
| Transparencia sede | `https://sevillalanueva.sedelectronica.es/transparency` | eHome | Sección urbanismo sin dataset scrapeable |
| Visor CM planeamiento | `http://www.madrid.org/cartografia/planea/planeamiento/html/web/VisorPlaneamiento.htm` | Visor web | Referencia; sin API REST por expediente |
| SIT CM WFS | `https://idem.comunidad.madrid/geoserver3/ows` (`sitcm:VPLA_V_AMBITO`) | WFS GeoJSON | Geometría partial por código ámbito |

## Fuentes detalladas

### 1. Web corporativa — Planeamiento (WordPress)

- **URL semilla:** `/planeamiento/`
- **Contenido:** 20 PDFs de Normas Subsidiarias 2001: normativa, 6 planos de ordenación (P1–P6), modificaciones puntuales nº 1, 3, 4, 7, 12, anexos, catálogo e inventario SNU.
- **Mecanismo:** enlaces directos a `wp-content/uploads/2016/09/` y `2020/05/`.
- **Fechas:** inferidas del path (`2016/09`) o del contenido (NNSS aprobadas 11/01/2001).

### 2. Web — Avance PGOU

- **URL:** `/urbanismo/avance-plan-general-de-ordenacion-urbana/`
- **Contenido:** 7 PDFs en Dropbox (Vol. 1 docs 1–6 + Vol. 2 medio ambiente) + carpeta compartida Dropbox.
- **Contexto:** sometido a información pública (noticia municipal 2024–2025).
- **Limitación:** alojamiento externo (Dropbox); URLs estables pero fuera del dominio municipal.

### 3. Sede electrónica eHome — Tablón

- **URL:** `https://sevillalanueva.sedelectronica.es/board/`
- **Formato:** tabla HTML: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
- **Enlaces:** `preview-document/{uuid}`.
- **Contenido vigente (jul 2026):** ~10 filas; mayoría personal/padrones. Urbanismo: expropiación Biocorredor (BOCM 01/07/2026).
- **Limitación:** solo anuncios vigentes; sin histórico indexable.

### 4. Licencias

No hay listado tabular de concesiones con coordenadas.

- Página `/urbanismo/tramites/` describe tipos: licencias menores/mayores, nueva planta, cédulas, apertura, disciplina urbanística.
- `/tramites-de-urbanismo-solicitudes-licencias/` enlaza a sede (certificado digital).
- Concesiones publicadas en tablón cuando proceda (filtro licencia/obra).

### 5. Transparencia sede

- `/transparency` incluye bloque «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» sin enlaces scrapeables a expedientes en CI.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS SIT Comunidad de Madrid — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='SEVILLA LA NUEVA'` (37 polígonos, códigos SAU-*, UE-*, API-1). Query con `srsName=EPSG:4326`, `outputFormat=application/json`.
- **Estrategia:** tras scrape, si el título cita código de ámbito (p. ej. `UE-15 VALDELAGUA`, `Zona 08`, `SAU-1`) → consulta WFS y rellena `geom_geojson`. Visor CM (`VisorPlaneamiento.htm`) enlazado desde trámites pero sin endpoint REST por expediente.
- **Limitaciones:** PDFs/planos sin georreferencia embebida; tablón sin coords; Dropbox PGOU sin GIS; matching WFS depende de mención de código ámbito en título.

## Limitaciones generales

- Sede homepage con redirect loop desde CI (`/catalog`); tablón `/board/` accesible.
- Tablón mayoritariamente no urbanístico en el momento de la investigación.
- Sin dataset abierto municipal de licencias con coordenadas.

## Referencia adapters

- WordPress + eHome tablón: `brunete.py`, `hoyo_de_manzanares.py`
- WFS SIT partial: `paracuellos_de_jarama.py`, `san_sebastian_de_los_reyes.py`
