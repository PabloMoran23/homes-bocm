# Villa del Prado — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `villa-del-prado` |
| Web corporativa | https://www.villadelprado.es (Joomla + Gantry5) |
| Portal transparencia | http://transparencia.villadelprado.org (Joomla + Gantry Helium) |
| Sede electrónica | https://sede.villadelprado.es (eAdmin add4u — **inaccesible**) |
| Boletín | BOCM (`boletin_source_id: bocm`) |

## Fuentes identificadas

### Proyectos / planeamiento

1. **Transparencia → Urbanismo** — `http://transparencia.villadelprado.org/index.php/urbanismo`
   - PGOU vigente (enlaces a Comunidad de Madrid `madrid.org/cartografia/planea/.../Villa_del_Prado/Vigente/`)
   - Plan Especial Ámbitos Territoriales A, B y D del SNU de las NNSS (PDFs locales + Google Drive)
   - Modificación proyecto parcelación **Las Hoyas** (BOCM-20230711-124, memoria PDF)
   - **Plan Parcial Sector 02 La Florida** (BOCM 2026, estudios en Google Drive)
   - Listado HTML estático con enlaces `<a href>` a PDF, Drive y BOCM

2. **PGOU Comunidad de Madrid** — documentación normativa histórica (catálogo, memoria, normas, planos)

### Licencias

- No hay listado público de concesiones de licencia.
- **Impresos y solicitudes** (web corporativa):
  - `/tu-ayuntamiento/impresos-y-solicitudes/577-licencia-obra-mayor`
  - `/tu-ayuntamiento/impresos-y-solicitudes/162-obra-menor`
  - `/tu-ayuntamiento/impresos-y-solicitudes/900-cartel-identificativo-obras-online`
- **Tablón sede** (`/eAdmin/Tablon.do?action=inicioTablon`) enlazado desde transparencia pero el host `sede.villadelprado.es` responde con *connection reset* (HTTP y HTTPS) desde red externa.

### Estrategia de ingesta

- Crawl determinista de la página de urbanismo en transparencia: extraer enlaces con texto y contexto de sección.
- Páginas informativas de trámites de licencia en la web corporativa (sin concesiones publicadas).
- Enriquecimiento de geometría vía WFS SITCM Comunidad de Madrid cuando el título menciona códigos de ámbito (UE-XX, S-XX) o nombres de sector.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDEM Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='VILLA DEL PRADO'`
  - 29 polígonos de ámbitos de planeamiento (UE-01…UE-24, S-01…S-04)
- **Estrategia:** `resolve_ambito_geometry()` / matching por código UE/S en títulos de expedientes; centroide WGS84 (`EPSG:4326`).
- **Limitaciones:**
  - Sin visor urbanístico municipal interactivo enlazado a expedientes.
  - Sede electrónica inaccesible (no tablón scrapeable).
  - Documentos PGOU en PDF sin georreferencia directa; solo ámbitos SITCM cuando el nombre/código coincide.
  - Google Drive no automatizable de forma fiable.

## Limitaciones generales

- Sede `sede.villadelprado.es`: TLS/HTTP reset (bloqueo o caída del servicio).
- Transparencia en HTTP (no HTTPS en dominio `.org`).
- Sin API JSON; solo HTML + PDFs.
- Paginación no aplicable (página única de urbanismo).
