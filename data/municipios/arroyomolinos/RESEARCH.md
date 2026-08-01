# Arroyomolinos — investigación portal ayuntamiento

Municipio: **Arroyomolinos** (`arroyomolinos`), Comunidad de Madrid, provincia Madrid.

> Nota: `www.arroyomolinos.es` corresponde al homónimo de Cáceres (Liferay Diputación de Cáceres). El municipio madrileño usa **`www.ayto-arroyomolinos.org`**.

## URLs base y páginas semilla

| Fuente | URL | Tecnología |
|--------|-----|------------|
| Web corporativa | https://www.ayto-arroyomolinos.org | Plone (Berger-Levrault) |
| Urbanismo (noticias) | https://www.ayto-arroyomolinos.org/ayuntamiento/concejalias/urbanismo-medio-ambiente-y-transportes/urbanismo | Plone — RSS + noticias planeamiento |
| Archivos urbanismo | `.../urbanismo/archivos/{año}` (2017–2025) | PDFs BOCM, diligencias, planes |
| Trámites licencias | https://www.ayto-arroyomolinos.org/servicios/tramites-municipales/tramites-urbanismo | Formularios PDF (calas, piscinas, fotovoltaica) |
| Sede electrónica | https://arroyomolinos.sedelectronica.es | espublico gestiona (add4u) |
| Tablón anuncios | https://arroyomolinos.sedelectronica.es/board | Wicket — tabla HTML con `preview-document/{uuid}` |
| Transparencia | https://arroyomolinos.sedelectronica.es/transparency | Wicket — sección 7 Urbanismo (1 doc) |
| Geoportal | https://www.ayto-arroyomolinos.org/.../geoportal | Enlace TecnoGeo (`tecnogeo.es`), visor estático |
| Consulta expedientes | https://arroyomolinos.sedelectronica.es/expedientes | Requiere identificación Cl@ve |

## Cómo se listan expedientes / proyectos

1. **RSS urbanismo** (`/urbanismo/noticias/rss.xml`): ~15 ítems con título, fecha, enlace a noticia Plone y PDFs/ZIP en `archivos/2025/`. Incluye expedientes (`Expte. 21386/2024`), planes especiales (SAU-4, UE6, NNSS).
2. **Archivos por año**: listado Plone con PDFs (`*.pdf/view`). Año 2025: ~23 documentos; 2021: 2; 2019: 1.
3. **Tablón sede** (`/board`): tabla paginada Wicket; columnas documento, expediente, procedimiento, categoría, descripción, fecha. Sin API JSON (a diferencia de sedes Insuit). Primera página ~10 anuncios (mayoría empleo/subvenciones).
4. **No hay** listado público de licencias concedidas; solo trámites informativos y tablón genérico.

## Cómo se publican licencias

- **Trámites informativos** en web Plone: calas, reapertura piscinas, fotovoltaica (PDFs descargables).
- **Tablón sede**: posibles edictos de licencia mezclados con otras materias; sin categoría «Urbanismo» fija en la muestra actual.
- **Consulta expedientes** en sede: autenticada, no scrapeable.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='ARROYOMOLINOS'`. Ámbitos: SAU-5, UE-2, APD-4, etc.
  - Geoportal municipal TecnoGeo: enlace visual en `/geoportal/visores/`; sin API/WFS pública enlazada al expediente.
- **Estrategia:** cruzar título del proyecto (códigos SAU-/UE-/APD-) con `DS_NOMB_AMB` en WFS; fallback ILIKE por fragmentos del título.
- **Limitaciones:** tablón y PDFs sin georreferencia; visor TecnoGeo no expone query por expediente; licencias sin polígono; geometría solo para planeamiento con código de ámbito reconocible.

## Limitaciones generales

- Homonimia con Arroyomolinos (Cáceres) en dominios genéricos.
- Tablón espublico sin endpoint JSON; paginación Wicket no implementada (solo primera página).
- Años de archivo 2022–2024 devuelven 404 en Plone.
- SSL sede: certificado gestionado; `insecure_ssl: true` por precaución en CI.
- Sin dataset de licencias históricas públicas.
