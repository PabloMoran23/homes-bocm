# Pinto — investigación portal ayuntamiento

**Municipio:** Pinto (Comunidad de Madrid)  
**Fecha:** 2026-06-19  
**BOCM regional (referencia):** 49 avisos

## Resumen

Pinto publica urbanismo en portales Liferay fragmentados (web corporativa + gobierno abierto). No hay tablón de anuncios accesible ni dataset de concesiones con coordenadas.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Biblioteca documental planeamiento | `https://gobiernoabierto.ayto-pinto.es/planeamiento-urbanistico` | Liferay DL (carpetas + `data-title`) | PGOU, planes parciales, especiales, estudios detalle, convenios (~128 PDFs) |
| Web corporativa — impresos urbanismo | `https://www.ayto-pinto.es/impresos-y-solicitudes/.../id/368979` | Liferay asset publisher + `/documents/` | Formularios licencia obra (trámites informativos) |
| Licencias y disciplina | `https://www.ayto-pinto.es/licencias-y-disciplina-urbanistica` | Liferay HTML + PDFs modelo | Trámites licencia (obra mayor/menor/parcelación) |
| Planes y programas | `https://gobiernoabierto.ayto-pinto.es/planes-programas` | Liferay + PDFs | Plan movilidad, agenda urbana |
| Sede electrónica | `https://sedeelectronica.ayto-pinto.es/` | Registro trámites | **Bloqueado** (connection reset / SSL) |

## Fuentes detalladas

### 1. Gobierno abierto — Planeamiento urbanístico (principal)

- **URL:** `https://gobiernoabierto.ayto-pinto.es/planeamiento-urbanistico`
- **Mecanismo:** Portlet `document_library` con carpetas:
  - 01 Texto PGOU, 02 Planos PGOU, 03 Desarrollos, 04 Modificaciones PGOU
  - 05 Planes Especiales, 06 Estudios de detalle, 07 Convenios urbanísticos
- **Extracción:** Crawl recursivo de `/planeamiento-urbanistico/-/document_library/kjPbdvcB2YEh/view/{folderId}`; enlaces `/documents/1618300/{uuid}?download=true` con atributo `data-title`.
- **Contenido:** ~128 documentos (memorias, planos, certificados aprobación, estudios detalle, convenios UE-54, etc.).

### 2. Impresos y solicitudes — Urbanismo

- **URL:** `https://www.ayto-pinto.es/impresos-y-solicitudes/-/asset_publisher/QAJT1uxGBlsu/content/id/368979`
- **Contenido:** ~14 modelos PDF (EMC-IG-0M9 a 0M22): licencia obra mayor, comunicación previa, parcelación, etc.
- **Limitación:** Son formularios de solicitud, no concesiones publicadas.

### 3. Licencias y disciplina urbanística

- **URL:** `https://www.ayto-pinto.es/licencias-y-disciplina-urbanistica`
- **Contenido:** 3 modelos PDF adicionales (obra mayor, menor, parcelación).
- **Limitación:** Página informativa; sin listado de licencias concedidas con fecha/distrito.

### 4. Fuentes descartadas / bloqueadas

| Fuente | Motivo |
|--------|--------|
| `sedeelectronica.ayto-pinto.es` | Connection reset / SSL handshake falla desde CI |
| `gobiernoabierto.ayto-pinto.es/BOCM` | Recopilación BOCM regional (no re-parsear BOCM) |
| `www.agendaurbanapinto.com` | Certificado autofirmado; fuera del dominio ayuntamiento |
| Pipeline Madrid (`sector_geometry/madrid_*`) | Fuera de alcance |

## Estrategia de ingesta

- **proyectos.jsonl:** biblioteca documental planeamiento (carpetas PGOU, PE, estudios detalle, convenios) + PDFs urbanos de planes-programas.
- **licencias.jsonl:** impresos urbanismo + modelos licencia (trámites informativos; sin concesiones con coordenadas).
- **IDs:** `pinto-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento` en todos los registros.

## Paridad esperada

- `proyectos`: ok (≥100 filas desde biblioteca documental).
- `licencias`: partial (formularios/trámites; sin concesiones publicadas).
