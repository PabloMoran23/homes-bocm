# Alpedrete — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.alpedrete.es/ | WordPress (tema propio), categoría Urbanismo y Obras |
| Urbanismo (RSS) | https://www.alpedrete.es/informacion-cat/urbanismo-y-obras/feed/ | RSS público (~10 posts), PGOU y obras |
| PGOU aprobación inicial | https://www.alpedrete.es/aprobacion-inicial-plan-general-de-ordenacion-urbana/ | PDF BOCM + documentación IP |
| Impresos / trámites | https://www.alpedrete.es/portal-de-tramites/impresos/ | Formularios licencias, DR urbanísticas, obra mayor |
| Sede eAdmin | https://carpeta.alpedrete.es/eAdmin/Sede.do | Carpeta ciudadano + registro telemático |
| Tablón anuncios | https://carpeta.alpedrete.es/eAdmin/Tablon.do?action=verAnuncios | HTML tabla eAdmin (ISO-8859-1), ~28 anuncios |
| Visor SITCM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Visor regional planeamiento Madrid |

**Nota:** La sede `carpeta.alpedrete.es` presenta certificado SSL con cadena incompleta; el adapter usa `insecure_ssl: true` (patrón Getafe/Chapinería).

## Expedientes / proyectos

- **Tablón eAdmin:** tabla HTML con título, periodo de exposición y enlace `verAnuncio&id=`. PDFs vía `abrirOriginal(token)` → `ValidarDocumento.do`. Sección "Urbanismo" con pocos anuncios vigentes.
- **WordPress:** posts de PGOU (aprobación inicial, resolución alegaciones) con PDFs en `/wp-content/uploads/`.
- **SITCM WFS:** 34 ámbitos (`UA-XX`, `SR-XX.X`) con polígonos en WFS Comunidad de Madrid.
- **RSS urbanismo:** noticias de obras municipales (asfaltado, parques) mezcladas con PGOU; filtradas por regex urbanística.

## Licencias

- No hay dataset público de concesiones otorgadas.
- **Impresos WP:** licencia de obras, declaraciones responsables urbanísticas, primera ocupación, obra mayor, tala arbolado, etc.
- **Tablón:** sin edictos de licencias recientes (mayoría JGL/contratación).
- El adapter devuelve páginas informativas de impresos + tablón filtrado.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='ALPEDRETE'`
  - Campo ámbito: `DS_NOMB_AMB` (ej. `UA-07 NUTRISA`, `SR-07.N LOS HUERTOS / EL NOGAL`)
- **Estrategia:** descarga masiva WFS por municipio (34 polígonos); enriquecimiento por código UA/SR o ILIKE en título del tablón/post.
- **Limitaciones:**
  - 34 polígonos SITCM sin enlace directo expediente↔geometría en sede.
  - Tablón e impresos no exponen coordenadas.
  - PGOU solo PDF sin georreferencia embebida.
  - Certificado SSL sede requiere `insecure_ssl`.

## Limitaciones generales

- Sede eAdmin codificación ISO-8859-1.
- WP REST API requiere autenticación (401); se usa RSS + scrape HTML.
- Sin API JSON de expedientes; scrape HTML determinista.
- Licencias: solo trámites informativos, no concesiones publicadas.
