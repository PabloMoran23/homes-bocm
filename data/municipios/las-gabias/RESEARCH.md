# Las Gabias — investigación portal ayuntamiento

**Municipio:** Las Gabias (Granada, Andalucía)  
**Slug:** `las-gabias`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)  
**INE:** 18124

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.lasgabias.es | Operativa — WordPress (Apache) |
| Portal transparencia | https://www.lasgabias.es/portal-transparencia/ | Operativa — WordPress multisite, REST API `/wp-json/` |
| Urbanismo (transparencia) | https://www.lasgabias.es/portal-transparencia/transparencia-en-materia-de-urbanismo-obras-publicas-y-medioambiente/ | Operativa — 25 subsecciones (planeamiento, innovaciones, calificaciones ambientales, expedientes IP) |
| Planeamiento | https://www.lasgabias.es/portal-transparencia/.../planeamiento-y-disciplina-urbanistica/ | Operativa — PDFs innovaciones PGOU, IOUD, plan parcial, ordenanzas |
| PGOU general | https://www.lasgabias.es/portal-transparencia/.../planeamiento-general-de-las-gabias/ | Operativa — enlace consulta Junta + cartografía PDF |
| Sede electrónica | https://lasgabias.sedelectronica.es | Operativa — espublico gestiona (eHome) |
| Tablón de anuncios | https://lasgabias.sedelectronica.es/board/ | Operativa — tabla HTML + preview-document |
| Catálogo trámites | https://lasgabias.sedelectronica.es/dossier | Operativa — catálogo sede |
| Consulta expedientes | https://lasgabias.sedelectronica.es/expedientes | Requiere autenticación |
| Sede legacy (SWAL) | https://sedeelectronica.lasgabias.es | Operativa — ASP.NET; trámites ciudadano, sin tablón público scrapeable |

## Portal transparencia (WordPress)

- **CMS:** WordPress multisite (`/portal-transparencia/`), tema The7.
- **API:** `https://www.lasgabias.es/portal-transparencia/wp-json/wp/v2/pages/{id}`.
- **Raíz urbanismo:** página ID `1942` con 25 hijas (planeamiento, innovaciones nº5/nº9 PGOU, calificaciones ambientales, expedientes en información pública, proyectos municipales, etc.).
- **Contenido:** enlaces directos a PDFs en `wp-content/uploads/sites/8/` (memorias, planos, edictos, aprobaciones BOJA).
- **Ejemplos:** Innovación/modificación puntual nº9 PGOU (2023–2026), plan parcial zona deportiva, PP San Javier, expropiación vial Carlos Cano.

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Antas, Alcaucín, Alhaurín el Grande.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~7 filas).

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Expediente | Procedimiento | Descripción |
|-------|------------|---------------|-------------|
| 04/08/2026 | 2332/2026 | Expropiaciones Forzosas | Declaración urgencia ocupación vial Carlos Cano |
| 03/08/2026 | 2332/2026 | Expropiaciones Forzosas | Certificado acuerdo expropiación vial Carlos Cano |

## Licencias de obra

- No hay dataset público de concesiones de obra con coordenadas.
- Trámites informativos vía sede (`/dossier`, `/citaprevia`) y consulta expedientes (login).
- Las licencias concedidas publicadas aparecen en el tablón como edictos (cuando existan).

## Proyectos / planeamiento

- **PGOU:** adaptación parcial LOUA (2009) + innovaciones puntuales nº5 y nº9 documentadas en transparencia.
- **Instrumentos:** plan parcial zona deportiva, PP San Javier, modificaciones puntuales.
- **Calificaciones ambientales:** secciones dedicadas con documentación IP.
- **Junta de Andalucía:** enlace a consulta planes urbanísticos desde planeamiento general.
- **SITUA:** visor regional de planeamiento (sin API por expediente municipal).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): `https://ws132.juntadeandalucia.es/situadifusion/` — visor PGOU regional sin consulta REST/WFS por código de expediente ayuntamiento.
  - Portal transparencia: cartografía solo en PDFs (planos situación, zonificación, alineaciones).
  - Sede espublico: documentos sin georreferencia.
- **Estrategia:** no hay MapServer/FeatureServer/WFS consultable por código de expediente. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Planos urbanísticos en PDF sin coordenadas embebidas.
  - Consulta de expedientes requiere login.
  - Tablón paginado con AJAX Wicket (solo primera página).

## Limitaciones generales

- Sin geometría por expediente.
- Histórico de licencias concedidas no publicado como listado estructurado.
- Dos sedes electrónicas (espublico + SWAL legacy); el adapter usa espublico como fuente principal.

## Adapter implementado

- `municipio.adapters.las_gabias:LasGabiasAyuntamientoAdapter`
- Fuentes: WP transparencia (crawl recursivo desde página 1942) + tablón espublico + páginas informativas sede.
