# Almendralejo — investigación portal ayuntamiento

## Identificación

| Campo | Valor |
|-------|--------|
| Slug | `almendralejo` |
| Provincia | Badajoz |
| CCAA | Extremadura |
| Web | https://www.almendralejo.es |
| Sede | https://almendralejo.sedelectronica.es (espublico gestiona / eHome) |
| Geoportal | https://mapas.almendralejo.es/geoportal/ |

## Fuentes y semillas

### Web municipal (`www.almendralejo.es`)

- CMS PHP propio (concejalías por `contenido.php?id_area=`).
- **Urbanismo:** `contenido.php?id_area=22` — descripción de servicios (licencias, planeamiento).
- Bloques laterales: Protocolo de Actuaciones Urbanísticas (`id_bloque=47`), Carteles (`48`).
- Acceso sede: `nuevasede.php` → botón a sede electrónica.
- Transparencia integrada: `transparencia.php` (enlace desde menú).

### Sede electrónica (`almendralejo.sedelectronica.es`)

- Plataforma **espublico gestiona** (Wicket, cookies de sesión necesarias en `/dossier`).
- **Tablón de anuncios:** `/board` — tabla HTML con `preview-document/{uuid}` (pocos anuncios urbanísticos en scraping oct-2026; mayoría personal/organización).
- **Trámites:** `/dossier` — catálogo `/catalog/t/...` con licencias de obra, comunicación previa, certificados urbanísticos, instancias de planeamiento.
- **Transparencia:** secciones UUID, p. ej. actas de pleno y junta de gobierno (PDF vía `preview-document`).
- Menú: `/expedientes` (consulta autenticada), `/citizen-service/...` (Urbanismo, Obras e Infraestructuras — enlaces informativos).

### Geoportal urbanístico

- **URL:** https://mapas.almendralejo.es/geoportal/ (cliente **Enmapa**, Nexus Geographics).
- **Backend:** GeoServer en `https://mapas.almendralejo.es/geoserver/ows` (WMS/WFS públicos).
- Capas relevantes (namespace `almendralejogis`):
  - `cad_parcela_a` — parcelas catastrales (`refcat`, `pcat1`, geometría polígonal).
  - `bt_municipios_a` — límite municipal.
  - `dt_usossuelo_a` — ocupación/uso del suelo (cartografía, no expedientes).
  - Grupos visor: Planeamiento, Topográfico, Cartografía de referencia.

## Cómo se listan datos

| Tipo | Mecanismo |
|------|-----------|
| Licencias concesionadas | Tablón `/board` cuando se publican edictos (HTML + PDF preview). En oct-2026 casi vacío de urbanismo. |
| Licencias (trámites) | Catálogo `/dossier` — páginas informativas de solicitud (no registro de concesiones). |
| Proyectos / planeamiento | Trámites de planeamiento en dossier; actas pleno/junta en transparencia; documentación web + visor geoportal. |
| Expedientes | Carpeta ciudadana / consulta sede (`/expedientes`) — requiere identificación. |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer `almendralejogis:cad_parcela_a` — polígono por referencia catastral (`refcat`), consulta `CQL_FILTER`.
  - WFS `almendralejogis:bt_municipios_a` — contorno municipal (enriquecimiento del registro del geoportal).
  - Visor Enmapa — capas de planeamiento sin API de enlace directo expediente↔geometría.
- **Estrategia adapter:**
  1. Si título/expediente contiene referencia catastral → query WFS parcela.
  2. Registro del geoportal urbanístico → contorno municipal WFS.
- **Limitaciones:**
  - Tablón sin coordenadas ni refcat en la mayoría de anuncios.
  - `cad_parcela_a.num_exp` vacío en muestras WFS (sin enlace automático expediente municipal).
  - No hay capa pública de ámbitos PGOU por código de expediente.
  - Sede `/dossier` responde lento (~7s) y requiere cookie jar (redirect 302 sin cookies).

## Limitaciones generales

- Sin boletín regional asociado en cola BOCM (`bocm_count: 0`).
- Sede antigua `sede.almendralejo.es` no resuelve DNS; solo sede nueva.
- SSL sede: certificado válido; se mantiene `insecure_ssl: true` por compatibilidad con patrón espublico en CI.
