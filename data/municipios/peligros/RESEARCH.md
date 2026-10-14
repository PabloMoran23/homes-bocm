# Peligros — investigación portal ayuntamiento

**Municipio:** Peligros (Granada, Andalucía)  
**Slug:** `peligros`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://ayuntamientopeligros.es | **Operativa** — WordPress (creadostheme) |
| Sede electrónica | https://peligros.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://peligros.sedelectronica.es/board | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://peligros.sedelectronica.es/dossier | **Operativa** (lento en CI) |
| Consulta expedientes | https://peligros.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Transparencia urbanismo | https://ayuntamientopeligros.es/portal-de-transparencia/urbanismo-obras-publicas-y-medio-ambiente/ | PEVG, estudios de detalle, planos PDF |
| Impresos | http://ayuntamientopeligros.es/impresos/ | Formularios varios |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor planeamiento Junta de Andalucía |
| Diputación Granada | https://www.dipgra.es/municipios/asistencia-a-municipios/asistencia/asistencia-urbanistica/planeamiento-urbanistico/ | Asistencia planeamiento provincial |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Alhendín y otros municipios granadinos.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}` (PDF en visor sede).
- **Paginación:** ~10 filas visibles; botón «Mostrar más» vía Wicket AJAX (adapter parsea primera página).

### Ejemplos urbanísticos encontrados (sep 2026)

| Fecha | Expediente | Procedimiento | Descripción |
|-------|------------|---------------|-------------|
| 10/09/2026 | 5574/2026 | Licencias de Actividad | Calificación ambiental restaurante Avda Granada, 3 P.I. |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites vía sede (`/dossier`) e impresos web (`/impresos/`).
- Las licencias concedidas publicadas aparecen en el tablón como edictos (p. ej. licencias de actividad).

## Proyectos / planeamiento

- **Transparencia:** Plan Especial Vega de Granada (PEVG), estudio de detalle, planos de clasificación de suelo, información pública (PDFs en `/wp-content/uploads/2020/03/`).
- **Tablón:** edictos y anuncios de licencias / actividad cuando proceda.
- **Junta Andalucía:** consulta planeamiento vía SITUA.
- **Diputación Granada:** asistencia técnica en planeamiento.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA / SituaDIFusión (Junta de Andalucía): planeamiento aprobado por municipio; sin campo de enlace a expediente del tablón.
  - Transparencia municipal: planos PDF del PEVG sin servicio WMS/WFS público.
  - Tablón espublico: PDFs sin georreferencia embebida.
- **Estrategia:** los visores regionales muestran zonificación agregada, **sin enlace a expediente** municipal. Los anuncios son PDF sin coords.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por código de expediente.
  - Consulta expedientes en sede requiere login.
  - Tablón paginado con AJAX Wicket (solo primera página en adapter).
  - El orquestador aplicará centroide municipio (37.2322, -3.6865) + jitter.

## Limitaciones generales

- Sin listado histórico público de licencias concedidas (solo trámites + tablón).
- `/dossier` puede ser lento (>40 s) en CI.
- Dominio `www.ayuntamientodepeligros.es` no resuelve; usar `ayuntamientopeligros.es`.

## Adapter implementado

- `municipio/adapters/peligros.py` — WordPress transparencia + tablón espublico + seeds PEVG/SITUA/Diputación.
