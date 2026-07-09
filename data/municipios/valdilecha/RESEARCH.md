# Valdilecha — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (Neosoft) | https://www.valdilecha.org | CMS corporativo |
| Urbanismo / PGOU | https://www.valdilecha.org/urbanismo | Normas, planos y fichas PGOU (PDF estáticos) |
| Bandos y anuncios | https://www.valdilecha.org/pleno-municipal/bandos-y-anuncios | Edictos BOCM/BOE: estudios de detalle, planes parciales, convenios, licencias |
| Sede eAdmin (Maggioli) | https://valdilecha.eadministracion.es/ | Trámites electrónicos; tablón en SPA Angular |
| Portal tributario | https://tributosvaldilecha.eadministracion.es/ | Solo tributos (no urbanismo) |

## Listado de expedientes / proyectos

- **Bandos y anuncios:** HTML Neosoft con secciones en negrita (`<strong>` / `font-weight:bold`) y enlaces a `/Ficheros/Documentos/*.pdf`. Títulos en atributo `tittle` del `<a>` o texto del enlace; contexto de sección (p. ej. «ESTUDIO DE DETALLE CALLE PALACIO 9»).
- **PGOU:** listado fijo de capítulos y planos en `/urbanismo` (sin paginación).
- **Sede eAdmin:** `Tablon.do?action=verAnuncios` y rutas `/api/*` devuelven el shell Angular (sin tabla HTML ni JSON público de anuncios sin sesión).

## Licencias

- No hay dataset público de concesiones con dirección/coords.
- `/urbanismo` publica formularios informativos: instancia general, declaración responsable urbanística, modelo autorización.
- Bandos incluyen anuncios puntuales de licencia (p. ej. farmacia, paintball) como PDF BOCM.
- Trámites reales vía sede eAdmin (registro electrónico).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid IDEM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='VALDILECHA'`
  - Campo ámbito: `DS_NOMB_AMB` (21 polígonos: AA-1…AA-10, SUS-R1, SUS-R-2…, APD-I1, etc.)
- **Estrategia:** cruzar título del anuncio/PDF con código de ámbito PGOU (p. ej. «Sector SUS R2» → `SUS-R-2`, «A.A-2» → `AA-2`) y descargar geometría WFS (`outputFormat=application/json`, `srsName=EPSG:4326`).
- **Limitaciones:**
  - Sin visor urbanístico municipal ni ArcGIS por expediente.
  - Estudios de detalle y licencias puntuales no tienen polígono en WFS (solo ámbitos del PGOU).
  - Sede eAdmin no expone geometría.
  - PDFs del tablón sin georreferencia embebida.

## Limitaciones generales

- Sede eAdmin migrada a SPA; scrape del tablón digital no determinista sin API pública.
- Muchos bandos son presupuestos/ordenanzas no urbanísticas — el adapter filtra por regex urbanismo.
- Fechas inferidas de nombres de fichero (`BOCM-YYYYMMDD-NN`) cuando no hay fecha en HTML.
