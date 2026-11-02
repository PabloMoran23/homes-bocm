# Camas — investigación portal ayuntamiento

**Municipio:** Camas (Sevilla, Andalucía)  
**Slug:** `camas`  
**Boletín:** sin boletín asociado en cola (`bocm_count: 0`)  
**INE:** 41021 (CIF municipal `P4102100G`)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.camas.es | **Operativa** — OpenCMS InPro (theme7) |
| Urbanismo | https://www.camas.es/es/urbanismo/ | Noticias y enlaces temáticos |
| PGOM (redirect) | https://www.camas.es/es/pgom | Redirige a portal participación |
| Portal PGOM | https://camas.nuevoplan.es | **Operativa** — WordPress; redacción PGOM (LISTA / Diputación Sevilla) |
| Sede electrónica | https://camas.sedelectronica.es | **Operativa** — espublico gestiona (DIR3 `L01410212`) |
| Tablón de anuncios | https://camas.sedelectronica.es/board | **Operativa** — tabla HTML + `preview-document` |
| Transparencia sede | https://camas.sedelectronica.es/transparency | Índice transparencia (Wicket); enlace desde web |
| Trámites | https://camas.sedelectronica.es/dossier | Catálogo procedimientos (licencias vía sede) |
| Licencias Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4102100G | LicytalPub provincial |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional Junta de Andalucía |
| Consulta expedientes | https://camas.sedelectronica.es/expedientes | Requiere certificado / identificación |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), mismo patrón que Tomares, Mairena del Aljarafe.
- **Listado:** tabla HTML con `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** `preview-document/{uuid}`.
- **Contenido urbanístico (nov 2026):** procedimiento «Planeamiento de Desarrollo» (p. ej. consulta pública PRI AUSU-13, exp. 7142/2021).
- **SSL:** certificado de sede con cadena no verificable en algunos entornos; adapter usa `insecure_ssl: true`.

## Planeamiento / proyectos

- **PGOM:** portal `camas.nuevoplan.es` con documentos PDF de participación (guía, doc. fase 1).
- **OpenCMS:** sección `/es/urbanismo/` (noticias; pocos PDFs directos en semillas).
- **Tablón:** anuncios de información pública / avance de instrumentos de planeamiento.

## Licencias de obra

- No hay dataset municipal histórico de concesiones con coordenadas.
- **Portal provincial:** Diputación de Sevilla LicytalPub CIF `P4102100G`.
- Edictos puntuales en tablón sede (cuando proceda).
- Trámites vía sede `/dossier` y `/expedientes` (autenticación).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal (ArcGIS/WFS) en web, sede ni PGOM.
  - SITUA/VITUA (Junta de Andalucía): cartografía regional; sin enlace por código de expediente del tablón.
  - Documentación PGOM y tablón son PDF/HTML sin georreferencia enlazable.
- **Estrategia:** el orquestador aplicará centroide municipio + jitter (`centroid` en manifest).
- **Limitaciones:**
  - Transparencia sede: árbol Wicket AJAX para subcarpetas (solo índice raíz scrapeado).
  - LicytalPub provincial no scrapeable de forma determinista.

## Limitaciones generales

- Tablón: primera página HTML visible (sin paginación detectada en scrape).
- Consulta de expedientes requiere login.
- Sin entradas BOCM/BOJA en histórico del pipeline para este municipio.

## Adapter implementado

- `municipio.adapters.camas:CamasAyuntamientoAdapter`
- Fuentes: tablón sede + PDFs PGOM + semillas OpenCMS urbanismo + índice transparencia sede + SITUA + páginas informativas licencias.
- IDs: `camas-lic-*` / `camas-proy-*` (sha256[:14]).
