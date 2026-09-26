# Antas — investigación portal ayuntamiento

**Municipio:** Antas (Almería, Andalucía)  
**Slug:** `antas`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)  
**INE:** 04011

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.antas.es | **Operativa** — WordPress (Astra + Elementor), REST API `/wp-json/` |
| Urbanismo | https://www.antas.es/urbanismo/ | **Operativa** — modelos DR obras, comunicación previa, cita previa |
| Ordenanzas | https://www.antas.es/reglamentos/ | **Operativa** — PDFs ordenanzas fiscales y urbanísticas |
| Sede electrónica | https://antas.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://antas.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Transparencia (PBOM) | https://antas.sedelectronica.es/transparency/666d54b8-d709-4596-94e1-242f69de5fc7/ | **Operativa** — documentos PBOM y EAE |
| Catálogo trámites | https://antas.sedelectronica.es/dossier.14 | Redirige/lento en CI |
| Cita previa urbanismo | https://antas.sedelectronica.es/citaprevia.1 | Operativa |
| Consulta expedientes | https://antas.sedelectronica.es/expedientes | Requiere autenticación |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Vera, Cómpeta, Lepe.
- **Listado:** tabla HTML con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente)
  - `class_folderName` (procedimiento)
  - `class_boardCategory` (categoría)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~6 filas).

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Documento | Descripción |
|-------|-----------|-------------|
| — | BANDO LIMPIEZA SOLARES 2026 | Bando municipal limpieza solares y terrenos urbanos |
| — | BANDOS 2026-0003 | Bando limpieza terrenos prevención incendios |

## Licencias de obra

- No hay dataset público de concesiones de obra con coordenadas.
- Trámites informativos:
  - Página urbanismo con modelos DR (obras escasa entidad, comunicación previa, cambio de uso).
  - Cita previa vía sede (`/citaprevia.1`).
  - Catálogo trámites sede (`/dossier.14`).
- Las licencias concedidas publicadas aparecen en el tablón como bandos/edictos (cuando existan).

## Proyectos / planeamiento

- **PBOM:** Plan Básico de Ordenación Municipal aprobado inicialmente (2025); documentos en portal transparencia sede.
- **PGOU histórico:** modificaciones puntuales (sector SR-6, polígono industrial Aljoroque SR-1).
- **Evaluación ambiental:** documentos EAE 18/23 en transparencia.
- **Noticias web:** artículos WordPress con PDFs adjuntos (PGOU, PBOM, bandos urbanísticos).
- **Ordenanzas:** PDFs urbanísticos en `/reglamentos/` (tasa licencia urbanística, intervención urbanística, habitabilidad, etc.).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): `https://ws132.juntadeandalucia.es/situadifusion/` — sin datos accesibles para INE 04011 (PBOM reciente, no indexado en visor compartido).
  - Web municipal: sin visor urbanístico ArcGIS/WFS enlazado a expedientes.
  - Transparencia y noticias: documentos PDF sin georreferencia embebida.
- **Estrategia:** no hay MapServer/FeatureServer/WFS consultable por código de expediente. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - PBOM recién aprobado; cartografía solo en PDFs del plan.
  - Consulta de expedientes requiere login.
  - Tablón paginado con AJAX Wicket (solo primera página).

## Limitaciones generales

- Sin geometría por expediente.
- Histórico de licencias concedidas no publicado como listado estructurado.
- `/dossier.14` inestable (timeout) en entorno CI.

## Adapter implementado

- `municipio.adapters.antas:AntasAyuntamientoAdapter`
- Fuentes: tablón sede + transparencia PBOM + noticias WordPress + ordenanzas urbanísticas + modelos DR.
- IDs: `antas-lic-*` / `antas-proy-*` (sha256[:14]).
