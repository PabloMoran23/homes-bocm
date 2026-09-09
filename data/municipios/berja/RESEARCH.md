# Berja — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Municipio | Berja (Almería, Andalucía) |
| INE | 04029 |
| CMS | CMSDIP-PRO (IBM Domino/XPages) — Diputación Provincial de Almería |
| Parámetro sede | `p=Berja` (listados); `p=SedeBerja` en algunos documentos |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Portal sede (Diputación) | https://www.dipalme.org/Servicios/cmsdipro/index.nsf/index.xsp?p=Berja | Inicio sede electrónica |
| Tablón reciente | https://www.dipalme.org/Servicios/cmsdipro/index.nsf/tablon_view_entidad_rol.xsp?p=Berja | ~30 anuncios (HTML `tablon-container`) |
| Tablón histórico | https://www.dipalme.org/Servicios/cmsdipro/index.nsf/tablonhp_view.xsp?p=Berja | Árbol por años (requiere POST XSP para expandir) |
| Tablón por categoría | https://www.dipalme.org/Servicios/cmsdipro/index.nsf/tablon_view_categoria123.xsp?p=Berja | Territorio, Audiencia IP, Autorizaciones y Licencias |
| Normas / planeamiento | https://www.dipalme.org/Servicios/cmsdipro/index.nsf/tablon_view_entidad_categoria1.xsp?p=Berja&cat=Normas | Ordenanzas, Planeamiento Urbanístico, Reglamentos |
| Noticias obras públicas | https://www.dipalme.org/Servicios/cmsdipro/index.nsf/noticias_view_entidad_categoria.xsp?p=Berja&cat=OBRAS+PÚBLICAS | Proyectos/obras municipales (~30/página, paginación XSP) |
| Transparencia | https://www.dipalme.org/Servicios/cmsdipro/index.nsf/portal_transparencia.xsp?p=berja | Enlaces a tablón y normativa |
| Web municipal | https://www.berja.es | **Timeout desde CI**; redirige a sede Diputación |
| berja.sedelectronica.es | https://berja.sedelectronica.es | Sede indeterminada (no usable) |
| SITUA Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=4029 | Planeamiento digitalizado (JSF, no scrapeado) |

## Cómo se listan expedientes

- **Tablón oficial (CMSDIP):** HTML con bloques `div.tablon-container` → enlace `tablon.xsp?p=Berja&documentId=…`, título en atributo `title`, categoría en `<p>` (ej. `Territorio - …`, `Autorizaciones y Licencias - …`).
- **Noticias obras:** `noticias.xsp?p=Berja&documentId=…` con fecha `DD/MM/YYYY` en `<span>` previo al título.
- **Documento individual:** `tablon.xsp` incluye `<h1>`, línea `Publicado: DD/MM/YYYY`, PDFs en `/Servicios/Tablon/Tablon.nsf/…`.
- **Listados con `p=SedeBerja`:** frecuentes timeouts; usar `p=Berja` en el adapter.

## Licencias

- Categoría tablón **Autorizaciones y Licencias** en `tablon_view_categoria123.xsp`.
- No hay listado dedicado accesible sin POST XSP; el tablón reciente rara vez incluye licencias.
- El adapter devuelve páginas informativas de trámites (índice sede, normas) cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Diputación Almería: `https://app.dipalme.org/geoserver/urbanismo/ows`
  - Capa: `urbanismo:v_siu_ambitos_o_sectores`
  - Filtro: `cod_ine='04029'` (38 sectores/UE en Berja)
  - Visor: https://app.dipalme.org/visor-gis/
- **Estrategia:** descarga WFS GeoJSON (EPSG:4326); sectores como polígonos `MultiPolygon`; enriquecimiento por coincidencia de nombre de sector en título del expediente.
- **Limitaciones:** sin geometría por expediente individual en el tablón; SITUA requiere sesión JSF; `www.berja.es` no responde en CI.

## Limitaciones

- `www.berja.es` y URLs con `p=SedeBerja` suelen hacer timeout (>60s) desde entornos cloud.
- Tablón histórico y categorías requieren POST XSP (IBM Domino) para expandir nodos; implementación parcial.
- Licencias: mayoría informativas; concesiones en PDFs del tablón o plenos (anexos dipalme.org).
- Paginación noticias: máx. 5 páginas configuradas en manifest.
