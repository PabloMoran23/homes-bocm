# Vícar — investigación portal ayuntamiento

Municipio: **Vícar** (`vicar`), provincia Almería, Andalucía. Boletín: BOJA (`boletin_source_id: boja`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.vicar.es |
| Área de Urbanismo (WP) | https://www.vicar.es/area-de-urbanismo/ |
| Sede electrónica (espublico gestiona) | https://vicar.sedelectronica.es |
| Tablón de anuncios | https://vicar.sedelectronica.es/board |
| Catálogo trámites | https://vicar.sedelectronica.es/dossier |
| Catálogo Urbanismo | https://vicar.sedelectronica.es/catalog/t/ae05799c-df61-43d1-be43-31943561cea9 |
| Transparencia (urbanismo) | https://vicar.sedelectronica.es/transparency/844bd0dd-f793-4a75-a0d6-b2a05d464eae/ , https://vicar.sedelectronica.es/transparency/36dedbe2-be61-4916-b4ac-9bfbbe3fac9d/ , https://vicar.sedelectronica.es/transparency/8b07db53-fe91-44a2-bfe1-52c4a0325a69/ |
| PAI / agenda urbana | https://pai.vicar.es/ |
| BOP Diputación (edictos ayto.) | https://app.dipalme.org/bop/publico.zul?procedencia=AYUNTAMIENTO%20DE%20VICAR |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |

## Expedientes / proyectos

- **Tablón sede:** HTML tabular (clases `class_name`, `class_folderName`, …), enlaces a `/preview-document/{uuid}`. Paginación limitada en página principal (~8 filas recientes en nov-2026).
- **No hay** listado público de expedientes urbanísticos (ruta `/expedientes` requiere identificación).
- **Web WP:** página de urbanismo informativa; sin PDFs de planeamiento enlazados directamente en la página (nov-2026).
- **Transparencia:** secciones de urbanismo accesibles pero sin documentos `preview-document` indexados en el scrape inicial.
- **Edictos urbanísticos** ocasionales en tablón (p. ej. información pública calificación ambiental).

## Licencias

- Concesiones vía **tablón** (categorías «Declaraciones Responsables o Comunicaciones…», «Seguridad Pública» para comercio ambulante, etc.).
- **Dossier sede:** trámites de licencia de obra, comunicaciones previas y actividad (presentación electrónica); no hay histórico descargable agregado.
- Sin dataset abierto de licencias con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Diputación de Almería: `urbanismo:v_siu_ambitos_o_sectores` con `cod_ine='04102'` (33 sectores urbanísticos con polígono EPSG:4326).
  - URL ejemplo: `https://app.dipalme.org/geoserver/urbanismo/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=urbanismo:v_siu_ambitos_o_sectores&CQL_FILTER=cod_ine%3D%2704102%27&outputFormat=application/json&srsName=EPSG:4326`
  - Campo enlace: código `sector` en propiedades (p. ej. `S-1`, `S-LL-3`, `SECTOR-I COSARIO`).
- **Estrategia:** filas de proyecto desde WFS (sectores SIU) + enriquecimiento por coincidencia de código de sector en título del tablón.
- **Limitaciones:** geometría a nivel **sector/planeamiento**, no por expediente individual; tablón y licencias sin GIS; consulta expedientes con login.

## Limitaciones técnicas

- Certificado TLS de `*.sedelectronica.es`: adapter usa `insecure_ssl: true` (patrón Getafe/Huércal Almería).
- Tablón con pocas filas urbanísticas recientes; mayoría personal/seguridad pública.
- `cod_ine` oficial en WFS Dipalme es **04102** (no 04097).

## Adapter

`municipio.adapters.vicar:VicarAyuntamientoAdapter` — patrón Huércal de Almería (espublico + Dipalme WFS).
