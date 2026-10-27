# la Vila Joiosa / Villajoyosa — investigación portal

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.villajoyosa.com |
| Urbanismo y Vivienda | https://www.villajoyosa.com/departamento/urbanismo/ |
| Tablón (landing web) | https://www.villajoyosa.com/tablon-de-anuncios/ |
| Categoría noticias urbanismo | https://www.villajoyosa.com/category/urbanismo-e-infraestructuras/ |
| Guía urbana | https://www.villajoyosa.com/guia-urbana/ |
| Buscador de trámites | https://www.villajoyosa.com/buscador-de-tramites/ |
| Sede electrónica | https://sede.villajoyosa.com |
| Tablón STA (dataset embebido) | https://sede.villajoyosa.com/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all |
| Catálogo STA | https://sede.villajoyosa.com/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |
| Registro planeamiento GVA (03139) | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03139%20LA%20VILA%20JOIOSA/ |

## Cómo se listan expedientes / proyectos

1. **Noticias WordPress** en la categoría *Urbanismo e infraestructuras*: anuncios de información pública, audiencia/reparcelación (p. ej. UE-2 PP-11), modificaciones PGOU, sectores TS-2 Montiboli, PR-7 Montesol. HTML + `article:published_time`; a veces PDF en `wp-content/uploads`.
2. **Sede STA — tablón** (`var dataset_PTS2_TABLON`): ~11 entradas históricas; pocas urbanísticas (ordenanza paisaje urbano, subvenciones). Detalle vía `DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`.
3. **Generalitat — registro planeamiento**: índice Apache con subcarpetas/PDFs del municipio 03139 (documentación PGOU aprobada).
4. **PDFs en departamento Urbanismo**: formularios de licencia, tasas urbanísticas, ordenanzas (no listado de expedientes en curso).

No hay visor de expedientes público (consulta de expedientes requiere certificado en PTS_EXPEDIENTES).

## Licencias de obra

- No hay dataset público de concesiones (como tablón de licencias con dirección).
- Trámites: formularios PDF en web de Urbanismo (licencia obra menor, declaración responsable primera ocupación, etc.) y sede STA (catálogo `CATSERV` **vacío** en la fecha de investigación).
- El adapter documenta páginas de trámite + PDFs de solicitud; no filas de concesión con fecha/dirección.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Guía urbana: solo iframe Google Maps (ayuntamiento), sin capas urbanísticas.
  - ICV WFS `InventarioSuSuz` (`terramapas.icv.gva.es/0702_Planeamiento/wfs`): filtros `CQL_FILTER` por `cod_ine_mun='03139'` no aplican en el servidor (devuelve otros municipios); no hay join fiable expediente↔polígono.
  - Visor GVA genérico sin enlace por código de expediente municipal.
- **Estrategia adapter:** sin `_fetch_geometry`; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** SSL autofirmado en `sede.villajoyosa.com` (`sede_insecure_ssl: true`); WP REST (`/wp-json/`) devuelve 503 a bots — scrape HTML de categorías.

## Limitaciones generales

- Certificado SSL inválido en sede STA.
- Catálogo telemático de trámites sin procedimientos publicados en JSON embebido.
- Boletín regional: sin entradas BOCM asociadas en cola (`bocm_count: 0`).
