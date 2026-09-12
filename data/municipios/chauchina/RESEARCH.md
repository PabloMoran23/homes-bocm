# Chauchina — investigación portal ayuntamiento

**Municipio:** Chauchina (Granada, Andalucía)  
**Slug:** `chauchina`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 18061

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://chauchina.es | **Operativa** — Mobirise Website Builder v6 |
| Urbanismo | https://chauchina.es/urbanismo.html | **Operativa** — trámites e impresos (sin PDFs descargables) |
| Sede electrónica | https://chauchina.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://chauchina.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Transparencia sede | https://chauchina.sedelectronica.es/transparency/ | **Operativa** — sección «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (103 docs, Wicket AJAX) |
| Transparencia Dip. Granada | https://www.dipgra.es/servicios/areas/transparencia/transparencia-municipal/chauchina/index.html | **Operativa** — NNSS PDF y ordenanzas |
| Cita previa | https://chauchina.sedelectronica.es/citaprevia | Redirige a citaprevia.0 |
| Catálogo trámites | https://chauchina.sedelectronica.es/dossier | Redirige a dossier.0 |
| Consulta expedientes | https://chauchina.sedelectronica.es/expedientes | Requiere autenticación Cl@ve/certificado |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Antas, Vera, Almuñécar.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos encontrados (sep 2026)

| Fecha | Expediente | Documento |
|-------|------------|-----------|
| 2026-08-10 | 1326/2026 | Aprobación inicial ordenanza reguladora funcionamiento registro de entidades urbanísticas colaboradoras |

## Licencias de obra

- No hay dataset público de concesiones de obra con coordenadas.
- Trámites informativos en `urbanismo.html`: licencia obra mayor/menor, actividad, parcelación, DR, etc.
- Cita previa vía sede (`/citaprevia`).
- Consulta de expedientes requiere login; sin listado público de licencias concedidas.

## Proyectos / planeamiento

- **PGOU-AP Chauchina:** innovaciones publicadas en BOJA (Punto Limpio 2023; reubicación usos equipamentales 2025).
- **NNSS:** PDF en transparencia Diputación de Granada (`normas-subsidiarias-transparencia.pdf`).
- **SITUA:** visor regional Junta de Andalucía para consulta PGOU (sin query por expediente del tablón).
- **Transparencia sede:** sección urbanismo con 103 documentos; navegación vía Wicket AJAX (no scrapeable sin sesión completa).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA (`https://ws132.juntadeandalucia.es/situadifusion/`): planeamiento regional; sin enlace por código de expediente del tablón municipal.
  - Web municipal y sede: sin visor urbanístico ArcGIS/WFS enlazado a expedientes.
  - Diputación Granada: PDFs de planeamiento sin georreferencia embebida.
- **Estrategia:** no hay MapServer/FeatureServer/WFS consultable por código de expediente. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Cartografía solo en PDFs del plan (NNSS, BOJA).
  - Consulta de expedientes requiere login.
  - Transparencia urbanismo cargada por AJAX Wicket.
  - Tablón paginado (solo primera página en adapter).

## Limitaciones generales

- Sin geometría por expediente.
- Histórico de licencias concedidas no publicado como listado estructurado.
- Web Mobirise sin API REST ni datos abiertos urbanísticos.

## Adapter implementado

- `municipio.adapters.chauchina:ChauchinaAyuntamientoAdapter`
- Fuentes: tablón sede + NNSS Dip. Granada + metadatos PGOU (BOJA) + enlace SITUA + páginas trámite.
- IDs: `chauchina-lic-*` / `chauchina-proy-*` (sha256[:14]).
