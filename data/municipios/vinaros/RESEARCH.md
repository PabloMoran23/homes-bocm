# Vinaròs — investigación portal ayuntamiento

**Municipio:** Vinaròs (Castellón, Comunitat Valenciana)  
**Slug:** `vinaros`  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)  
**INE:** 12138

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.vinaros.es | **Operativa** — Drupal 8 |
| Portal urbanismo | https://urbanisme.vinaros.es | **Operativa** — Drupal 8 (tema Ibis), subdominio dedicado |
| Sede electrónica | https://vinaros.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://vinaros.sedelectronica.es/board | **Operativa** — ~10 filas (sep 2026), incluye Actuacions Urbanístiques |
| Transparencia | https://vinaros.sedelectronica.es/transparency/242d282a-b692-4d0a-926b-88bec2b7af1a/ | Carpeta urbanismo |
| Catálogo trámites | https://vinaros.sedelectronica.es/dossier | Lento en CI |
| Consulta expedientes | https://vinaros.sedelectronica.es/expedientes | Requiere Cl@ve |
| Geoportal municipal | https://geoportal.vinaros.es | Catálogo de mapas (sin REST/ArcGIS expuesto en HTML) |
| Agenda urbana | https://agendaurbana.vinaros.es | Planificación estratégica (no expedientes) |
| PGOU 2001 | https://urbanisme.vinaros.es/es/contenido/planeamiento-urbanistico-municipal | Textos en SharePoint + ZIP visor local |
| Modificaciones PGOU | https://urbanisme.vinaros.es/es/contenido/modificaciones-del-pgou-2001 | Carpetas SharePoint por modificación puntual |
| Planes parciales | https://urbanisme.vinaros.es/es/contenido/planes-parciales-i-planes-de-reforma-interior | SharePoint |
| PAI/PAA | https://urbanisme.vinaros.es/es/node/302 | SharePoint |
| Resoluciones | https://urbanisme.vinaros.es/es/node/275 | SharePoint |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Alcalà de Xivert/Burriana.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Contenido actual (sep 2026):** actuaciones urbanísticas (asfaltado, alumbrado sectores 5-6), además de personal y subvenciones.

## Licencias de obra

- No hay dataset público histórico de concesiones con coordenadas.
- Trámites informativos: portal urbanisme.vinaros.es y catálogo sede `/dossier`.
- Las licencias concedidas aparecen en el tablón como edictos cuando se publican.

## Proyectos / planeamiento

- **PGOU 2001:** textos por títulos en SharePoint (`vinaros.sharepoint.com/s/info_publica`) + ZIP `202609-Web Planeamiento.zip` y visor RAR en Drupal.
- **Modificaciones puntuales:** al menos 33 modificaciones documentadas (MP n.º5, n.º14, n.º33, Camping Vinaròs, Ciudad del transporte-SUI06, etc.).
- **Planes parciales, PAI, estudios de detalle, planes especiales:** enlaces SharePoint en subpáginas Drupal.
- **ICV Inventario SU-SUZ:** 88 sectores/unidades de ejecución del municipio en WFS regional (`cod_ine_mun=12138`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz`: `https://terramapas.icv.gva.es/0702_Planeamiento` (`outputFormat=GML3`, `srsName=EPSG:4326`). Filtro por `cod_ine_mun=12138` en cliente (CQL del servidor no es fiable).
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
  - Visor municipal: archivo RAR `Visor_1.rar` en Drupal (aplicación de escritorio, no servicio web).
  - Geoportal: `https://geoportal.vinaros.es` — catálogo estático sin capas REST scrapeables.
- **Estrategia:** descargar 88 ámbitos SU/SUZ del inventario regional ICV; emparejar por código SUI/SUR/UE en títulos de tablón o Drupal cuando sea posible.
- **Limitaciones:**
  - Inventario regional informativo (sin enlace a expediente del tablón).
  - Documentación PGOU en SharePoint (no scrapeable sin autenticación).
  - Visor local RAR no integrable en pipeline web.
  - Tablón paginado (solo primera página en adapter).

## Limitaciones generales

- Bilingüismo valenciano/castellano en sede y web.
- Consulta de expedientes requiere login Cl@ve.
- `/dossier` puede dar timeout en entorno CI.

## Adapter implementado

- `municipio.adapters.vinaros:VinarosAyuntamientoAdapter`
- Fuentes: ICV WFS InventarioSuSuz + Drupal urbanisme (SharePoint/ZIP) + tablón sede + páginas informativas de trámites.
