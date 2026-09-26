# Fuente Palmera — investigación portal ayuntamiento

## Municipio

- **Nombre:** Fuente Palmera
- **Provincia:** Córdoba (Andalucía)
- **INE:** 14032
- **BOJA:** 1 aviso en `ccaa_history_parsed_incremental.csv`

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web oficial | https://fuentepalmera.es |
| Urbanismo | https://fuentepalmera.es/urbanismo/ |
| Agenda Urbana | https://fuentepalmera.es/agenda-urbana/ |
| Bases y anuncios | https://fuentepalmera.es/bases-y-anuncios/ |
| Transparencia | https://transparencia.fuentepalmera.es/ |
| Sede electrónica | https://fuentepalmera.es/sede → https://sede.eprinsa.es/ftepalm |
| Tablón de edictos | https://sede.eprinsa.es/ftepalm/tablon-de-edictos |
| Trámites sede | https://sede.eprinsa.es/ftepalm/tramites |
| Consulta expedientes | https://sede.eprinsa.es/ftepalm/expedientes (requiere Cl@ve) |

## CMS y formato de datos

- **Web institucional:** WordPress + Divi (ePrinsa/Diputación de Córdoba). REST API pública en `/wp-json/wp/v2/`.
- **Urbanismo:** página estática con secciones (Plan Municipal de Vivienda y Suelo, modelos licencias, normativa e instrumentos urbanísticos). PDFs en `wp-content/uploads/`.
- **Modificación puntual 2025:** diligencia de aprobación publicada en web (`DILIGENCIA_APROBACIONmodificacion-puntual-fuente-palmera-para-ad-vers-4__Firmado.pdf`).
- **Noticias urbanismo:** categoría WP `47` (6 entradas históricas: revisión NNSS, estudios de detalle, etc.).
- **Licencias:** modelos de solicitud/declaración responsable en `/urbanismo/` (lc-01, dr-01..05, cp-01..02, AOE). No hay listado de concesiones publicadas.
- **Sede eprinsa:** Ember SPA (Diputación de Córdoba). Tablón y expedientes requieren sesión/token — no scrapeable sin browser (mismo patrón que La Carlota, Priego, Fernán Núñez).

## Expedientes / proyectos

1. **HTML urbanismo** — PDF modificación puntual normativa suelo no urbanizable (sep 2025).
2. **WP REST API** `GET /wp-json/wp/v2/posts?categories=47` — noticias urbanísticas históricas.
3. **WP búsqueda** `search=modificacion+puntual|planeamiento|urbanismo` — posts con actuaciones (MP NNSS 2020, estudios de detalle 2019, etc.).
4. **SITUA** — enlace genérico al visor regional Junta de Andalucía para PGOU.

## Licencias

- Modelos PDF en urbanismo: licencia obras, comunicación previa, declaraciones responsables, actividad ocasional.
- Tablón sede eprinsa inaccesible para scraping determinista.
- Trámites sede informativos (catálogo + consulta expedientes autenticada).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes investigadas:**
  - `mapserver.eprinsa.es` referenciado en CSP de la web (`frame-src`) pero sin capa pública enlazada a expedientes municipales.
  - Callejero turístico (`/callejero-de-fuente-palmera/`) sin geometría de ámbitos urbanísticos.
  - SITUA/VITUA Junta de Andalucía: visor regional de planeamiento, sin query por expediente municipal ni polígonos descargables por código.
  - PDFs y noticias sin ref. catastral ni coordenadas.
- **Estrategia:** orquestador aplicará centroide municipio + jitter (`centroid: [37.7050, -5.0999]`).
- **Limitaciones:** sin polígonos de ámbito en fuentes públicas; tablón sede requiere reverse-engineering API autenticada.

## Limitaciones

- Tablón edictos sede eprinsa no accesible sin sesión.
- Licencias mayoritariamente informativas (formularios), no registro de concesiones.
- Sin geometría GIS enlazable a expedientes.
