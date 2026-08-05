# Moralzarzal — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.moralzarzal.es/ | WordPress, área urbanismo informativa |
| Urbanismo | https://www.moralzarzal.es/urbanismo/ | Contacto y enlaces al área |
| Sede eAdmin | https://carpeta.moralzarzal.es/eAdmin/Sede.do | Carpeta ciudadano + registro telemático |
| Tablón anuncios | https://carpeta.moralzarzal.es/eAdmin/Tablon.do?action=verAnuncios | HTML tabla eAdmin (ISO-8859-1), 16 anuncios vigentes |
| Trámites urbanismo | https://tramites.moralzarzal.es/urbanismo-vivienda-y-medio-ambiente/ | WordPress Divi, trámites licencias/obras |
| Transparencia planeamiento | https://transparencia.moralzarzal.es/urbanismo-y-medio-ambiente/planeamiento/ | NNSS (ZIP planos), normas PDF |
| Visor SITCM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Visor regional planeamiento Madrid |

**Nota:** `moralzarzal.sedelectronica.es` redirige a selector genérico espublico (no operativo). La sede real es `carpeta.moralzarzal.es/eAdmin`.

## Expedientes / proyectos

- **Tablón eAdmin:** tabla HTML con título, periodo de exposición y enlace `verAnuncio&id=`. PDFs vía `abrirOriginal(token)` → `ValidarDocumento.do`.
- **Transparencia:** NNSS aprobadas (ZIP por hoja/plano 1072–1097) y `normas_de_planeamiento.pdf`.
- **SITCM WFS:** 222 ámbitos con códigos `API-X.SY-AZ` y `Z#-P#` (Actuaciones de Planeamiento Interés / zonas PGOU).
- **WP noticias:** comunicados de obras (Berrocal Sur, M-615) sin expediente estructurado.

## Licencias

- No hay dataset público de concesiones (como Madrid capital).
- **Trámites WP:** licencia mayor, licencias urbanísticas, declaración responsable primera ocupación, contenedores, etc.
- **Tablón:** anuncios puntuales (convenio gestión urbanismo, obras Berrocal Sur).
- El adapter devuelve páginas informativas de trámites + tablón filtrado.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='MORALZARZAL'`
  - Campo ámbito: `DS_NOMB_AMB` (ej. `API-9.S1-A6 HERREN DE LOS TOMILLOS`, `Z6-P11`)
- **Estrategia:** descarga masiva WFS por municipio; enriquecimiento por código API/Z o ILIKE en título del tablón.
- **Limitaciones:**
  - 222 polígonos SITCM pero sin enlace directo expediente↔geometría en sede.
  - Tablón y trámites no exponen coordenadas.
  - NNSS solo PDF/ZIP sin georreferencia embebida.
  - `moralzarzal.sedelectronica.es` no usable.

## Limitaciones generales

- Sede eAdmin codificación ISO-8859-1.
- Sin API JSON de expedientes; scrape HTML determinista.
- Licencias: solo trámites informativos, no concesiones publicadas.
- Paginación tablón: una página (~16 anuncios); búsqueda POST por término urbanístico.
