# Huércal de Almería — investigación portal ayuntamiento

**Municipio:** Huércal de Almería (Almería, Andalucía)  
**Slug:** `huercal-de-almeria`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)  
**INE:** 04053

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://ayuntamientohuercaldealmeria.com | **Redirige** a sede `/info`; rutas legacy (`/normas-subsidiarias/`) devuelven 500 |
| Sede electrónica | https://huercaldealmeria.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://huercaldealmeria.sedelectronica.es/board/ | **Operativa** — ~10 filas vigentes |
| Obras y Urbanismo | https://huercaldealmeria.sedelectronica.es/citizen-service/85e49f39-73da-4dda-8341-f7cb94132f7e | **Operativa** — trámites informativos licencias y planeamiento |
| Catálogo trámites | https://huercaldealmeria.sedelectronica.es/dossier | Lento/timeout ocasional en CI |
| Consulta expedientes | https://huercaldealmeria.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Transparencia sede | https://huercaldealmeria.sedelectronica.es/transparency | Enlace «Obras y Urbanismo» |
| WFS Diputación Almería | https://app.dipalme.org/geoserver/urbanismo/ows | **Operativa** — sectores SIU por `cod_ine=04053` |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional digitalizado |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Vera, Cómpeta, Alcaucín.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** ~10 anuncios vigentes (ago 2026); sin histórico amplio en primera página.

### Ejemplos encontrados (ago 2026)

| Fecha | Expediente | Procedimiento | Descripción |
|-------|------------|---------------|-------------|
| 18/08/2026 | 4763/2025 | Seguridad Pública | Aprobación inicial PTEL (Plan Territorial de Emergencia Local) |
| 28/08/2026 | — | Alteraciones de Bienes | Anuncio BOP aprobación definitiva |

## Licencias de obra

- No hay dataset público de concesiones de licencia de obra con coordenadas.
- Página informativa «Obras y Urbanismo» en sede: Declaraciones Responsables, Licencias Urbanísticas, Comunicación Previa, Planeamiento.
- Trámites de solicitud vía catálogo sede (`/dossier`); consulta de expedientes requiere Cl@ve.
- El adapter incluye páginas informativas del tablón y catálogo de trámites.

## Proyectos / planeamiento

- **Planeamiento vigente:** Normas Subsidiarias de Planeamiento (aprobadas 31/03/1999; adaptación parcial LOUA 27/12/2010). Municipio en redacción de nuevo PGOU.
- **Tablón:** PTEL (Plan Territorial Emergencia Local), alteraciones de bienes, subvenciones.
- **BOJA:** modificaciones de planeamiento general (p. ej. MP núm. 3 SNU-1AG, MP núm. 19 en tramitación 2026).
- **WFS Diputación:** 170 sectores/ámbitos SIU (`urbanismo:v_siu_ambitos_o_sectores`, `cod_ine=04053`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Diputación Almería: `urbanismo:v_siu_ambitos_o_sectores` filtrado por `cod_ine='04053'` — polígonos de sectores/ámbitos (UE-16, UE-AT-1, …) en EPSG:4326.
  - SITUA/VITUA (Junta de Andalucía): cartografía de planeamiento general; sin campo expediente del tablón.
- **Estrategia:** el adapter importa sectores SIU desde WFS Dipalme (con `geom_geojson`) y enriquece filas del tablón cuando el título menciona código de sector. Sin enlace expediente↔polígono en tablón PDF.
- **Limitaciones:**
  - Web corporativa legacy inaccesible (500).
  - Tablón sin georreferencia embebida en PDFs.
  - SITUA sin query REST por código de expediente municipal.
  - Licencias concedidas sin coordenadas públicas.

## Limitaciones generales

- Tablón con pocos anuncios vigentes (~10).
- Sin listado histórico público de licencias concedidas.
- `/dossier` puede ser lento en CI.
- `insecure_ssl: true` en sede (certificado intermedio).

## Adapter implementado

- `municipio.adapters.huercal_de_almeria:HuercalDeAlmeriaAyuntamientoAdapter`
- Fuentes: tablón sede + trámites informativos + WFS Diputación sectores + SITUA.
- IDs: `huercal-de-almeria-lic-*` / `huercal-de-almeria-proy-*` (sha256[:14]).
