# San Fernando de Henares — investigación portal ayuntamiento

**Municipio:** San Fernando de Henares (Comunidad de Madrid)  
**Slug:** `san-fernando-de-henares`  
**Web principal:** https://www.ayto-sanfernando.com  
**Fecha investigación:** 2026-06-19

## Resumen

El ayuntamiento publica urbanismo y licencias en un **portal WordPress (tema Divi)** sin API REST pública (iThemes Security bloquea `/wp-json`). Las fuentes scrapeables son:

1. **Tablón de anuncios** (HTML estático con fecha + enlace PDF)
2. **Área de planificación** (PDFs de PGOU, planes parciales, PE)
3. **Páginas informativas de trámites** de licencias urbanísticas
4. **Geoportal** Angular (solo mapa; sin listado de expedientes)

No hay registro público de concesiones de licencia con coordenadas. Las licencias del adapter son páginas de trámite (paridad informativa, como Pozuelo/Rivas).

## Fuentes

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón Ayuntamiento | https://www.ayto-sanfernando.com/tablon-anuncios-ayuntamiento/ | HTML (`<li>DD/MM/YYYY – <a href="pdf">`) | Edictos y anuncios municipales |
| Tablón otras admin. | https://www.ayto-sanfernando.com/tablon-anuncios-otras-administraciones/ | HTML igual | Anuncios de otras administraciones |
| Planificación | https://www.ayto-sanfernando.com/planificacion-de-la-ciudad-y-desarrollo-sostenible/ | HTML + PDFs | PGOU, PE, modificaciones plan parcial |
| Plan General | https://www.ayto-sanfernando.com/plan-general/ | HTML + PDF | Documentación PGOU |
| Trámites urbanismo | https://www.ayto-sanfernando.com/licencias-urbanismo/ | HTML | Índice de trámites (licencia, DR, certificación…) |
| Geoportal | https://geoportal.ayto-sanfernando.com | Angular SPA | Visor cartográfico; sin API de expedientes |
| Sede SAVIA | https://sanfernandohenares.savia.net | Login requerido | Tramitación electrónica (no scrapeable) |

## Formato tablón

```html
<li>18/6/2026 – <a href="https://www.ayto-sanfernando.com/wp-content/uploads/2026/06/....pdf">TÍTULO</a></li>
```

Fechas en `DD/MM/YYYY`. PDFs en `/wp-content/uploads/YYYY/MM/`.

## Limitaciones

- **Certificado SSL** del dominio principal inválido en algunos clientes → adapter usa `insecure_ssl: true`.
- **REST API WordPress** bloqueada (401 iThemes Security).
- **Tablón** con pocos anuncios recientes; la mayoría son fiscales/deportes, no urbanismo.
- **Licencias concedidas** no publicadas en listado; solo formularios/trámites informativos.
- **Geoportal** no expone listado de proyectos; solo capas cartográficas.
- **Sin coordenadas** en fuentes públicas → `lat`/`lon` y `distrito` quedan `null`.

## Estrategia adapter

- **proyectos:** tablón (filtro urbanismo) + PDFs de planificación/plan-general
- **licencias:** subpáginas de `licencias-urbanismo/` (trámites informativos)
- IDs estables: `sanfernando-{lic|proy}-{sha256[:14]}`

## Referencias consultadas

- `municipio/adapters/pozuelo.py` — Drupal expedientes IP
- `municipio/adapters/mostoles.py` — tablón sede + GMU
- `municipio/adapters/getafe.py` — sede STA + gobierno abierto
- `municipio/adapters/rivas_vaciamadrid.py` — WordPress HTML + tablón
