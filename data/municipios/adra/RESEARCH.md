# Adra — investigación portal ayuntamiento

**Municipio:** Adra (Almería, Andalucía)  
**Slug:** `adra`  
**Boletín:** sin boletín asociado en cola (`bocm_count: 0`)  
**INE:** 04003

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.adra.es | **Operativa** — Liferay CE 7.4 |
| Urbanismo (Liferay) | https://www.adra.es/web/guest/w/urbanismo1 | **Operativa** — contacto + enlace trámites |
| Sede electrónica | https://adra.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://adra.sedelectronica.es/board/ | **Operativa** — ~11 filas vigentes (oct 2026) |
| Urbanismo (sede) | https://adra.sedelectronica.es/citizen-service/a9e57573-a3a2-45d6-b510-88f22b9585db | **Operativa** — trámites informativos |
| Catálogo trámites | https://adra.sedelectronica.es/dossier | Timeout frecuente desde CI |
| Consulta expedientes | https://adra.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| WFS Diputación Almería | https://app.dipalme.org/geoserver/urbanismo/ows | **Operativa** — 101 sectores SIU (`cod_ine=04003`) |
| Visor GIS Dipalme | https://app.dipalme.org/visor-gis/ | Cartografía SIU provincial |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), mismo patrón que Huércal, Níjar, Mojácar.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Contenido urbanístico reciente:** escaso en primera página (empleo, plenos, ordenanzas de terrazas, edictos notariales).

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites vía sede (Declaración Responsable, licencias urbanísticas) y enlace «Trámites» en web Liferay (`/impresos-y-formularios`).
- El adapter incluye páginas informativas del tablón y catálogo de trámites; filas del tablón cuando el texto menciona licencia/obra.

## Proyectos / planeamiento

- **Web:** área «Urbanismo y Obras Públicas» con enlace al tablón en sede.
- **WFS Dipalme:** 101 ámbitos/sectores SIU (p. ej. `SI-5-LC`, `S.U.O. SI-1-PR-LC`, `SUNC 1-13.1-A`).
- **Tablón:** ordenanzas, edictos, convocatorias de pleno; pocos expedientes de planeamiento en vigencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `urbanismo:v_siu_ambitos_o_sectores` con `CQL_FILTER=cod_ine='04003'` — polígonos MultiPolygon EPSG:4326.
  - Visor provincial Dipalme (`app.dipalme.org/visor-gis/`).
  - SITUA (Junta): cartografía PGOU sin enlace a expediente del tablón.
- **Estrategia:** importar sectores SIU desde WFS (filas `proyectos` con `geom_geojson`) y enriquecer anuncios del tablón cuando el título menciona código de sector.
- **Limitaciones:**
  - Tablón sin georreferencia en PDFs.
  - `/dossier` inestable en red del agente.
  - Sin visor municipal propio con query por expediente.

## Limitaciones generales

- Tablón mayoritariamente no urbanístico en la página actual.
- Sin listado histórico público de licencias concedidas.
- `insecure_ssl: true` en sede (compatibilidad cadena certificados en CI).

## Adapter implementado

- `municipio.adapters.adra:AdraAyuntamientoAdapter`
- Fuentes: tablón sede + trámites informativos + WFS Dipalme sectores + páginas web/sede.
- IDs: `adra-lic-*` / `adra-proy-*` (sha256[:14]).
