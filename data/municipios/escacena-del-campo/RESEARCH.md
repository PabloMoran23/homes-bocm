# Escacena del Campo — investigación portal ayuntamiento

**Municipio:** Escacena del Campo (Huelva, Andalucía)  
**Slug:** `escacena-del-campo`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 21034

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.escacenadelcampo.es | **Operativa** — OpenCMS (SagaSuite, tema Diputación de Huelva); requiere `insecure_ssl` |
| Urbanismo | https://www.escacenadelcampo.es/es/Areas-tematicas/urbanismo/ | **Operativa** — sección informativa (contacto; sin PDFs indexados) |
| Ordenanzas | https://www.escacenadelcampo.es/es/ayuntamiento/ordenanzas/ | **Operativa** — página vacía de descargas en scraping |
| Publicaciones oficiales | https://www.escacenadelcampo.es/es/ayuntamiento/publicaciones-oficiales/ | **Operativa** — enlace a urbanismo |
| Portal transparencia | https://www.escacenadelcampo.es/es/gobierno-abierto/portal-transparencia/ | **Parcial** — indicadores LTA; URLs de resultados devuelven 404 |
| Sede electrónica | https://escacenadelcampo.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://escacenadelcampo.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://escacenadelcampo.sedelectronica.es/dossier/ | **Operativa** tras warm-up de sesión (`/board/`) |
| Consulta expedientes | https://escacenadelcampo.sedelectronica.es/expedientes | Requiere autenticación |
| SITUA (PGOU) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=21034 | **Operativa** — planeamiento general municipal |
| BOJA mod. PGOU | https://www.juntadeandalucia.es/boja/2022/134/32 | **Operativa** — modificación núm. 1 PGOU (2022) |

## CMS / sede

- **Web:** OpenCMS alojado en plantilla Diputación de Huelva (`com.saga.sagasuite.theme.diputacion.huelva.base`).
- **Sede:** espublico gestiona (Wicket/Java), misma plataforma que Antas, Cómpeta, Piñuécar-Gandullas.
- **Tablón:** columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`; enlaces `preview-document/{uuid}`.

### Ejemplos tablón (sep 2026)

| Fecha | Documento | Notas |
|-------|-----------|-------|
| 14/09/2026 | Convocatoria Pleno extraordinario | No urbanístico |
| 22/06/2026 | Edicto cobranza IAE 2026 | No urbanístico |
| 13/05/2026 | Enlace público censo de amianto | Urbanístico / medio ambiente |
| 13/02/2025 | Lista definitiva candidatos jurado | No urbanístico |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Catálogo `/dossier/` incluye trámites: licencia de obra, DR obras, licencias de actividad/ocupación, comunicaciones previas, etc. (páginas informativas, sin histórico de concesiones).
- Consulta de expedientes requiere identificación Cl@ve.

## Proyectos / planeamiento

- **PGOU:** consulta regional SITUA (cid=21034); aprobación modificación núm. 1 en BOJA 2022 (adaptación NNSS a LOUA).
- **Tablón:** censo de amianto (exp. 133/2025) como actuación urbanística publicada.
- **Trámites sede:** Solicitud de Actuación Urbanística, Certificado/Informe Urbanístico.
- **Web:** sin repositorio PBOM/PGOU local accesible; portal transparencia LTA con indicadores PGOU pero páginas de detalle rotas (404).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA: `https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=21034` — visor regional de planeamiento; sin API GeoJSON por expediente municipal.
  - VITUA (Junta): visor cartográfico regional; no enlazado a expedientes del ayuntamiento.
  - Web/sede: sin MapServer, WFS ni visor urbanístico municipal.
- **Estrategia:** no hay consulta determinista por código de expediente → polígono. Orquestador usará centroide municipio + jitter.
- **Limitaciones:** PDFs/planes solo en BOJA/SITUA; tablón sin geometría; `/dossier/` requiere cookie de sesión previa.

## Adapter implementado

- `municipio.adapters.escacena_del_campo:EscacenaDelCampoAyuntamientoAdapter`
- Fuentes: tablón sede + catálogo trámites + crawl web OpenCMS + SITUA + BOJA PGOU.
- IDs: `escacena-del-campo-lic-*` / `escacena-del-campo-proy-*` (sha256[:14]).
