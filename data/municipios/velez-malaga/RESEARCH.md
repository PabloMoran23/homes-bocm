# Vélez-Málaga — investigación portal ayuntamiento

## Resumen

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Tetraware) | https://www.velezmalaga.es | Área Urbanismo, tablón de anuncios con fichas `mod=urbanismo-infraestructuras-operativos&id=` |
| Tablón urbanismo | https://www.velezmalaga.es/?mod=urbanismo-infraestructuras-operativos&pos=1&tag=tablon-de-anuncios | Listado paginado (`pos=1..35`), ~10 expedientes/página, PDFs en ficha |
| Sede electrónica STA | https://sede.velezmalaga.es/sta/CarpetaPublic/ | PTS2_TABLON, CATALOGO — **403 Forbidden** desde entorno cloud del agente |
| Trámites urbanismo | https://www.velezmalaga.es/index.php?mod=urbanismo-infraestructuras-operativos&tag=solicitudes-de-urbanismo-en-la-sede-electronica | Enlaces a DR obras, certificado urbanístico, alineaciones (sin listado de licencias concedidas) |
| PGOU / normativa | https://www.velezmalaga.es/index.php?mod=normativamunicipal&tag=pgou | PGOU'96 vigente, revisión PGOU/19 y PGOM'26 en elaboración (PDFs y enlaces) |

## Cómo se listan expedientes

- CMS **Tetraware (TWSAINT)** en `velezmalaga.es`.
- El tablón publica entradas con `<a class="titulo doc" href="index.php?mod=urbanismo-infraestructuras-operativos&id=NNN">TÍTULO (EXPTE. …)</a>`.
- Paginación: `tag=tablon-de-anuncios&pos=N` (hasta ~35 páginas).
- Cada ficha incluye bloque «Enlaces y Descargas» con PDFs en `/contenido/datos/urbanismo-infraestructuras-operativos/`.
- Códigos habituales en título: `EXPTE. 13/2026/PLAN`, `EXP.4/24-PA`, sectores `SUP.VM-17`, unidades `UE.VM-11`.

## Licencias

- No hay dataset ni tablón público de **licencias concedidas** con dirección/coords.
- Las licencias y comunicaciones previas se tramitan en la sede STA (catálogo); el ayuntamiento solo enlaza trámites informativos desde la web.
- El adapter devuelve filas informativas (sede + página de solicitudes) y entradas del tablón cuyo título menciona licencia/actuación/obra cuando aplica.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Noticias oficiales (2024): nuevo servidor GIS y visor ciudadano previsto para 2025 — sin URL pública de MapServer/FeatureServer en la web.
  - PGOU'96: planos PDF estáticos (`normativamunicipal`), no GeoJSON/WFS por expediente.
  - PRP Diputación Málaga (`gis.prpmalaga.es`): visores provinciales de otros municipios de la comarca; no hay capa REST enlazable por código de expediente municipal.
  - VITUA (Junta de Andalucía): instrumentos LISTA/RIU; Vélez-Málaga sigue con PGOU'96 adaptado LOUA, sin geometría por expediente del tablón.
- **Estrategia:** centroide municipal en manifest (`centroid`) + jitter en orquestador `geocode`.
- **Limitaciones:** tablón solo PDF; sede bloqueada en CI; visor municipal no desplegado públicamente a fecha de investigación.

## Limitaciones técnicas

- `sede.velezmalaga.es`: WAF/403 en IP de cloud agent (PTS2_TABLON y CATALOGO).
- Fechas: muchas fichas sin fecha visible en HTML; se infiere año desde código de expediente en el título.
- Volumen tablón: ~345 entradas → `max_tablon_pages: 40` y `request_delay_s: 0.35` (~15–20 s de listado).

## Referencias implementación

- Patrón tablón + paginación: adapters con `max_tablon_pages` (p. ej. Almería, Cabanillas).
- STA bloqueado en CI: documentado como en Coín / Melilla (fallback web).
- Sin GIS: `geometry_status: unavailable` como Málaga capital / Coín en provincia.
