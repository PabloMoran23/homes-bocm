# Puente Genil — investigación portal ayuntamiento

## Municipio

- **Nombre:** Puente Genil
- **Provincia:** Córdoba (Andalucía)
- **Comunidad autónoma:** andalucia
- **Notas cola:** Sin boletín asociado en CSV BOCM (`bocm_count: 0`)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web oficial | https://puentegenil.es |
| Urbanismo, obras y viviendas | https://puentegenil.es/urbanismo-obras-y-viviendas/ |
| Normativa urbanística (PDFs PGOU/PE/ordenanzas) | https://puentegenil.es/urbanismo-obras-y-viviendas/normativa_urbanistica/ |
| Agenda Urbana / PEM | https://puentegenil.es/agenda-urbana-de-puente-genil-plan-estrategico-municipal/ |
| Registro entidades urbanísticas colaboradoras | https://puentegenil.es/registro-municipal-de-entidades-urbanisticas-colaboradoras/ |
| Bandos | https://puentegenil.es/bandos/ |
| Transparencia | https://puentegenil.es/transparencia/ |
| Sede electrónica | https://puentegenil.es/sede → https://sede.eprinsa.es/puentege |
| Tablón de edictos | https://sede.eprinsa.es/puentege/tablon-de-edictos |
| Trámites sede | https://sede.eprinsa.es/puentege/tramites |
| Consulta expedientes | https://sede.eprinsa.es/puentege/expedientes (requiere Cl@ve) |

## CMS y formato de datos

- **Web institucional:** WordPress + Divi (ePrinsa/Diputación de Córdoba). REST API en `/wp-json/wp/v2/`.
- **Normativa urbanística:** página estática con ~40 PDFs (PGOU aprobación definitiva 2024, planes parciales históricos, ordenanzas reguladoras de licencias y construcción).
- **Noticias:** categoría WP `29` (Urbanismo, 122 entradas) y `172` (Agenda Urbana).
- **Licencias:** ordenanzas y tasas de licencia urbanística en PDF; modelos vía sede. No hay registro público estructurado de concesiones.
- **Sede eprinsa:** aplicación Ember (Diputación Córdoba). Tablón de edictos carga vía SPA con token de sesión — no scrapeable con `urllib` (mismo patrón La Carlota, Fuente Palmera, Priego).

## Expedientes / proyectos

1. **HTML normativa urbanística** — instrumentos de planeamiento (PGOU, PE Río Genil, sistemas generales, calificaciones) y ordenanzas.
2. **WP REST** `GET /wp-json/wp/v2/posts?categories=29|172` — noticias y actuaciones urbanísticas.
3. **WP búsqueda** `search=planeamiento|urbanismo|modificacion` — posts relacionados.
4. **Bandos / agenda urbana** — PDFs y enlaces complementarios en páginas semilla.
5. **SITUA** — visor regional Junta de Andalucía para consulta PGOU (sin enlace por expediente municipal).

## Licencias

- Ordenanza reguladora de licencias urbanísticas y construcciones (PDF en normativa).
- Tablón sede eprinsa (edictos) no accesible para scraping determinista.
- Trámites sede: catálogo informativo + consulta expedientes autenticada.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes investigadas:**
  - Dashboard ArcGIS Agenda Urbana embebido en urbanismo: `https://spcpg.maps.arcgis.com/apps/dashboards/44d8fb7698aa4109bdd224df18c0b3da` — indicadores del PEM, sin capas descargables por código de expediente ni query REST enlazada a proyectos municipales.
  - SITUA/VITUA Junta de Andalucía: planeamiento regional, sin polígono por expediente del ayuntamiento.
  - PDFs de normativa y noticias WP sin referencia catastral/coordenadas scrapeables.
  - Sede eprinsa expedientes requiere autenticación.
- **Estrategia:** orquestador aplica centroide municipio + jitter (`centroid: [37.3891, -4.7669]` en manifest).
- **Limitaciones:** sin WFS/MapServer municipal público enlazado a listados HTML; tablón sede requiere reverse-engineering API autenticada.

## Limitaciones

- Tablón edictos sede eprinsa no accesible sin sesión Ember.
- Licencias mayoritariamente normativa/trámites informativos, no histórico de concesiones.
- Sin geometría GIS por expediente en fuentes públicas scrapeables.
