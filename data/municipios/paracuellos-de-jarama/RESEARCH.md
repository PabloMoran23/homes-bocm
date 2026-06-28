# Paracuellos de Jarama — investigación portal ayuntamiento

**Municipio:** Paracuellos de Jarama (Comunidad de Madrid)  
**Fecha:** 2026-06-24  
**BOCM regional (referencia):** 25 avisos

## Resumen

Paracuellos publica urbanismo en la **sede electrónica Insuit/add4u** (`sede.paracuellosdejarama.es`)
con tablón virtual JSON, catálogo de trámites y geoportal TecnoGeoWS. La web corporativa Drupal
(`www.paracuellosdejarama.es`) bloquea peticiones automatizadas (Cloudflare); la ingesta usa sede + WFS SIT.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Sede inicio | `https://sede.paracuellosdejarama.es/portal/entidades.do?ent_id=1&idioma=1` | HTML | Enlaces tablón, catálogo |
| Tablón virtual | `.../portal/noEstatica.do?opc_id=268` | POST JSON `tablonElectronico.do` | Edictos, urbanismo, bandos |
| API tablón | `POST /sede/tablonElectronico.do` | JSON (`listaDocumentos`, `listaExpedientes`) | Subsecciones: EDICTO, URB, BANDOS, … |
| Catálogo trámites | `.../sede/catalogoTramites.do?opcion=detalle&idApl=1` | HTML | Urbanismo (asu_mod_cod=1): 11 trámites |
| Ficha Planeamiento | `.../fichaInformativa.do?asu_cod=2&asu_mod_cod=1&tra_cod=1_1` | HTML | Trámite informativo |
| Geoportal urbanismo | `https://citymap.tecnogeows.com/user/101552155529107607471/map/Ap5eADbCMbtcq6PvpCRHdw` | SPA TecnoGeoWS | PGOU, parcelas, calles (sin API REST pública por expediente) |
| Web municipal PGOU/desarrollo | `https://paracuellosdejarama.es/es/planeamiento-desarrollo` | Drupal + PDFs | **Bloqueado** Cloudflare en CI |
| SIT CM WFS | `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO` | GeoJSON WFS | ~69 ámbitos planeamiento Paracuellos |

## Tablón virtual (`tablonElectronico.do`)

`POST` con `opcion=consultar`, `opc_id=268`, `subseccion={COD}`.

Subsecciones (jun 2026):

| Código | Nombre | Docs | Exp. |
|--------|--------|------|------|
| EDICTO | Edictos | 43 | 0 |
| URB | Urbanismo | 1 | 0 |
| BANDOS | Bandos | 5 | 0 |
| DEP | Deportes | 2 | 1 |
| … | … | … | … |

Documento urbanismo vigente en URB:

- `BOCM 29-11-2024 Aprob. Definitiva Plan Especial Camino de San Miguel 1B` (02/12/2024)
- URL verificación: `/portal/verificarDocumentos.do?codigo=266PE-02LXD-W7RT8&subseccion=URB`

Campos documento: `docNom`, `docFpu`, `docCve`, `docUrl`, `docId`.

## Trámites urbanismo (catálogo sede, idApl=1)

Trámites scrapeables como páginas informativas (sin listado histórico de concesiones):

- Planeamiento, Calificación Urbanística/PAE
- Licencias Urbanísticas de Obras, DRUO, DRUPO
- Segregación y agrupaciones, Legalización, Cédula Urbanística, …

## Licencias

No hay dataset abierto de concesiones georreferenciadas.

- Edictos de licencia en tablón cuando se publican (pocos en el periodo actual).
- Páginas de trámite del catálogo sede como referencia informativa.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geoportal TecnoGeoWS (`citymap.tecnogeows.com`) — parcelas y planeamiento vigente; SPA con token anónimo, sin enlace por código de expediente.
  - WFS SIT CM `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='PARACUELLOS DE JARAMA'` — polígonos de ámbitos (UE-*, AD-*, S-*, AN-*, …).
- **Estrategia adapter:** emparejar título del tablón con `DS_NOMB_AMB` / códigos de sector (`UE-11`, `AD-8`, …) vía WFS `CQL_FILTER` + `EPSG:4326`.
- **Limitaciones:**
  - Web Drupal bloqueada (Cloudflare) — no scrape de `/es/planeamiento-desarrollo` ni PDFs directos.
  - Geoportal TecnoGeo sin API REST documentada para expedientes.
  - Plan Especial Camino San Miguel 1B no tiene ámbito homónimo en SIT; geometría solo cuando el título coincide con código/nombre de ámbito.

## Limitaciones

- `www.paracuellosdejarama.es`: bloqueado Cloudflare (403) — documentar, no usar como fuente primaria.
- `pro.paracuellos.es`: DNS no resuelve desde CI.
- Tablón: histórico limitado a documentos publicados en subsecciones actuales (~44 docs total).
- Certificados PDF tablón: enlaces a verificador CSV, no descarga directa del PDF sin flujo web.

## Estrategia adapter

1. POST `tablonElectronico.do` por subsecciones (URB, EDICTO, …) filtrando urbanismo.
2. Catálogo `idApl=1` → fichas informativas trámites licencia/obra.
3. Enriquecer geometría vía WFS SIT cuando el título contiene código de ámbito.
4. IDs: `paracuellos-de-jarama-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón + trámites informativos: `pelabravo.py`, `san_fernando_de_henares.py`
- WFS SIT geometría: `sector_geometry/resolvers_madrid.py`
