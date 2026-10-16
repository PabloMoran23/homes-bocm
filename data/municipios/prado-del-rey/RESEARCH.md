# Prado del Rey — investigación portal ayuntamiento

**Municipio:** Prado del Rey (Cádiz, Andalucía)  
**Slug:** `prado-del-rey`  
**INE:** 11028 · **BOJA:** 1 entrada en histórico regional  

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.pradodelrey.es | Operativa (Joomla 5 + YOOtheme + Phoca Download) |
| PGOU | https://www.pradodelrey.es/index.php/homepage/pgou | Phoca Download — aprobación inicial PGOU (dic 2019), EAE, planos, memoria |
| Bandos y comunicados | https://www.pradodelrey.es/index.php/homepage/bandos-y-comunicados | PDFs (fiestas; sin urbanismo reciente) |
| Áreas y delegaciones | https://www.pradodelrey.es/index.php/homepage/areas-y-delegaciones | Delegación Urbanismo, Vías y Obras |
| Sede electrónica | https://pradodelrey.sedelectronica.es | Operativa — espublico gestiona (Indra eHome) |
| Tablón de anuncios | https://pradodelrey.sedelectronica.es/board/ | Tablón principal (pocas filas; mayoría administrativo) |
| Catálogo trámites | https://pradodelrey.sedelectronica.es/dossier | Formularios (sin listado histórico de licencias) |
| Perfil contratante Dip. Cádiz | https://www3.dipucadiz.es/perfiles/organismo/show/325 | Enlace desde web municipal |
| EPICSA (Dip. Cádiz) | https://www.dipucadiz.es/epicsa/ | Visor provincial (sin capa expediente municipal enlazable) |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=11028 | Planeamiento digitalizado regional |
| SITUA PGOU compartido | https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf?municipiosSeleccionados=11028&codigosMunicipios=11028 | Instrumento general municipal |
| VITUA (Junta) | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ | Visor urbanístico regional |

**Nota:** `www.pradodelrey.es` devuelve **403** a peticiones sin User-Agent de navegador (Apache/Plesk).

## Cómo se listan expedientes / proyectos

1. **PGOU (Phoca Download):** enlaces `?download={n}:{slug}` en `/homepage/pgou` — memoria, EAE, planos de ordenación, estudio movilidad, informes acústicos (aprox. 10 PDFs, subidos ene 2022).
2. **Tablón sede (`/board/`):** tabla HTML Wicket (Documento, Expediente, Procedimiento, Categoría, Fecha) con `/preview-document/{uuid}`. En la revisión (oct 2026) predominan anuncios de cobranza IAE; sin filas urbanísticas recientes.
3. **SITUA:** consulta por municipio INE 11028; documentos escaneados del planeamiento depositado en Junta (sin API JSON de expedientes municipales).
4. **Bandos web:** Phoca Download en `/homepage/bandos-y-comunicados` (contenido festivo/administrativo).

## Licencias de obra

- **No hay listado público** de licencias concedidas ni dataset abierto.
- Trámites en sede `/dossier` (licencias, comunicaciones previas) — solo formularios electrónicos.
- El tablón puede publicar edictos puntuales; adapter incluye páginas informativas de referencia (tablón + catálogo trámites).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **VITUA / SITUA (Junta):** clasificación y planeamiento a escala municipal/regional; no consulta por código de expediente del ayuntamiento.
  - **EPICSA (Diputación de Cádiz):** cartografía provincial; sin enlace a expedientes de Prado del Rey.
  - **PGOU PDF (Phoca):** planos raster en PDF, sin servicio WMS/ArcGIS municipal.
  - **Tablón sede:** metadatos textuales, sin coordenadas.
- **Estrategia:** sin visor municipal enlazable; el orquestador aplica centroide municipal + jitter (`centroid: [36.8898, -5.5542]`).
- **Limitaciones:** planeamiento publicado como PDF; sin geometría por expediente en portal; licencias no listadas.

## Limitaciones generales

- WAF en web municipal requiere User-Agent de navegador.
- Tablón con bajo volumen y poco contenido urbanístico.
- PGOU en tramitación/aprobación inicial (documentación 2019) — verificar estado en SITUA/BOJA.

## Adapter

- `municipio.adapters.prado_del_rey:PradoDelReyAyuntamientoAdapter`
- IDs: `prado-del-rey-lic-*` / `prado-del-rey-proy-*` (sha256[:14]).
