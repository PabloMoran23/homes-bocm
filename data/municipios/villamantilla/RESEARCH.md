# Villamantilla — investigación portal ayuntamiento

**Municipio:** Villamantilla (Comunidad de Madrid)  
**Fecha:** 2026-08-06  
**BOCM regional (referencia):** 8 avisos

## Resumen

Villamantilla publica información municipal en la **web Joomla Helix Ultimate**
(`www.villamantilla.org`) con tablón municipal vía **icagenda**, trámites en PDF y
sede electrónica **espublico gestiona** (`villamantilla.sedelectronica.es`).
Los ámbitos de planeamiento están en el **SIT de la Comunidad de Madrid**
(WFS `sitcm:VPLA_V_AMBITO`, código municipio 175).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.villamantilla.org` | Joomla Helix Ultimate + SP Page Builder | Portal general, normativa, trámites |
| Normativa urbanismo | `https://www.villamantilla.org/normativa/urbanismo` | Joomla categoría (vacía) + RSS | Sin documentos publicados actualmente |
| Tablón municipal | `https://www.villamantilla.org/inicio/tablon-municipal` | Joomla icagenda + RSS | Bandos, licitaciones, anuncios |
| Trámites | `https://www.villamantilla.org/tramites` | HTML estático | Formularios PDF (licencia de obra, etc.) |
| Tablón sede | `https://villamantilla.sedelectronica.es/board/` | HTML tabla | Vacío en agosto 2026 |
| Portal transparencia sede | `https://villamantilla.sedelectronica.es/transparency` | Wicket AJAX | Sección 7 URBANISMO (0 docs) |
| Visor SIT CM | `http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=175` | Enlace desde web | Planeamiento regional |
| SIT WFS | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 15 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='VILLAMANTILLA'` |
| Visor turístico municipal | `http://81.46.222.82:8080/quercus/sig-alberche/index-28175.php` | Quercus SIG | Turismo/gestor municipal (no enlazado a expedientes) |

## Tablón de anuncios

### Web municipal (icagenda)

Paginación `?start=10`. En agosto 2026 destacan:
- Bando limpieza y desbroce de parcelas 2026
- Licitación proyecto reasfaltado de calles y señalización horizontal
- Exposición pública modificación estatutos Mancomunidad El Alberche

### Sede electrónica (`/board`)

Tabla HTML vacía (`<tbody id="idd">` sin filas). Portal sede recién migrado (julio 2026).

## Licencias

- **Formulario PDF:** `SOLICITUD-DE-LICENCIA-DE-OBRA.pdf` en `/tramites`.
- **Sede electrónica:** catálogo de trámites en `/dossier` (espublico gestiona).
- No hay dataset histórico de concesiones con coordenadas.
- El adapter incluye páginas informativas de referencia (tablón sede, urbanismo, trámites, transparencia).

## Proyectos / planeamiento

- **SIT WFS:** 15 ámbitos (UE-1…UE-11, SAU-1…SAU-4) con polígonos WGS84.
- **Tablón:** bando parcelas, licitación reasfaltado viario.
- **Normativa urbanismo:** categoría Joomla vacía (RSS sin items).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='VILLAMANTILLA'` (`srsName=EPSG:4326`)
  - Visor regional SIT CM: `http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=175`
  - Visor turístico Quercus (IP municipal, sin enlace a expedientes)
- **Estrategia:** Semillas de ámbitos desde WFS; enriquecer por código UE/SAU en título cuando
  coincida con `DS_NOMB_AMB`.
- **Limitaciones:** Tablón/PDF sin georreferenciación; transparencia Wicket no automatizable;
  sede `/board` vacía; normativa urbanismo sin documentos publicados.

## Limitaciones

- Portal transparencia: árbol Wicket con sesión JS; sección urbanismo con 0 documentos.
- Tablón sede recién migrado y vacío.
- Normativa urbanismo Joomla sin PDFs ni artículos.
- Visor turístico Quercus no enlaza expedientes urbanísticos individuales.

## Estrategia adapter

1. RSS y paginación HTML del tablón municipal Joomla (icagenda).
2. Formularios PDF de licencia en `/tramites`.
3. Tablón sede `/board` (cuando tenga filas).
4. Semillas de ámbitos SIT WFS con `geom_geojson`.
5. Páginas informativas de referencia (tablón sede, urbanismo, trámites, transparencia).
6. IDs: `villamantilla-{lic|proy}-{sha256[:14]}`.
