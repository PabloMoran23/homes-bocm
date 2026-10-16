# Pozoblanco — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://pozoblanco.es | WordPress (Divi/Yoast); área Urbanismo |
| Normativa / planes | https://pozoblanco.es/areas-municipales/urbanismo/normas-y-planes-urbanisticos/ | Adaptación parcial PGOU a LOUA: memoria + decenas de planos PDF (`/wp-content/uploads/`) |
| Noticias urbanismo | WP REST `categories=54,97,93,100,104` | Noticias de obras, sector industrial, legalización polígonos |
| Portal transparencia | https://portal-transparencia.pozoblanco.es/planificacion/ | Plan estratégico; actas JGL con acuerdos de planeamiento (PDF) |
| Sede electrónica | https://sede.eprinsa.es/pozoblanco | Diputación Córdoba (eprinsa): trámites, tablón de edictos (SPA) |
| Tablón edictos | https://sede.eprinsa.es/pozoblanco/tablon-de-edictos | Edictos/licencias (carga Ember; sin API REST pública) |
| Consulta expedientes | https://sede.eprinsa.es/pozoblanco/expedientes | Solo interesados autenticados (Cl@ve/certificado) |
| SITUA JDA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=14051 | Buscador planeamiento digitalizado (sin hits visibles para este INE) |
| BOJA | vía pipeline BOCM/CCAA | 1 referencia histórica en cola (`boja`) |

## Listado de expedientes / proyectos

- **Planeamiento:** principalmente PDFs estáticos en la página de normas (HTML + enlaces directos).
- **Actuaciones recientes:** noticias WP categoría Urbanismo (JSON API).
- **Información pública / edictos:** tablón sede eprinsa (no scrapeable de forma determinista sin sesión/token del componente).

## Licencias

- Trámites en sede (licencia obra mayor/menor, escritos urbanismo) — ver informe transparencia 2023–2024 (cifras agregadas, no listado).
- No hay dataset abierto de concesiones con dirección/coords.
- Adapter expone páginas informativas del tablón y catálogo de trámites.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** SITUA (`cid=14051` INE), VITUA regional (sin enlace por expediente municipal), web municipal (solo PDFs/planos raster).
- **Estrategia:** N/A — polígonos no publicados en servicio consultable; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** Planos en PDF sin georreferencia WGS84; sede sin visor SIG; tablón sin geometría.

## Limitaciones técnicas

- Sede eprinsa: misma arquitectura Ember que otros municipios cordobeses (La Carlota, Priego): HTML shell sin filas en servidor.
- `sede.pozoblanco.es` no resuelve; canal alternativo `pozoblanco.sedelectronica.es` redirige a selector genérico.

## Adapter

- Módulo: `municipio/adapters/pozoblanco.py`
- Patrón: Priego de Córdoba / La Carlota (WP + PDF seeds + sede informativa).
