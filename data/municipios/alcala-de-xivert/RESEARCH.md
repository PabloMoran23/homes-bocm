# Alcalà de Xivert — investigación portal ayuntamiento

**Municipio:** Alcalà de Xivert (Castellón, Comunitat Valenciana)  
**Slug:** `alcala-de-xivert`  
**Boletín:** DOGV (`dogv`, 6 entradas en histórico)  
**INE:** 12004

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.alcaladexivert.es | **Operativa** — Drupal 9 (tema Toools) |
| Sede electrónica | https://alcaladexivert.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://alcaladexivert.sedelectronica.es/board | **Operativa** — ~10 filas (ago 2026), sin urbanismo reciente |
| Portal transparencia | https://alcaladexivert.sedelectronica.es/transparency | **Operativa** — carpeta 6. URBANISMO (235 docs), navegación Wicket AJAX |
| Catálogo trámites | https://alcaladexivert.sedelectronica.es/dossier | Lento en CI |
| Consulta expedientes | https://alcaladexivert.sedelectronica.es/expedientes | Requiere Cl@ve |
| PGOU (web) | https://www.alcaladexivert.es/es/pgou | Mapas PDF e1–e15, ZIP textos PGOU 1998 |
| Mapa interactivo PGOU | https://www.alcaladexivert.es/es/mapa-interactivo-pgou | Marcador OpenLayers (sin capas PGOU) |
| Urbanismo (carta servicios) | https://www.alcaladexivert.es/es/cartas-de-servicios/urbanismo | PDF carta de servicios |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta/Cártama.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Contenido actual (ago 2026):** principalmente personal, subvenciones y ordenanzas fiscales; sin licencias de obra publicadas en primera página.

## Licencias de obra

- No hay dataset público histórico de concesiones con coordenadas.
- Trámites informativos: carta de servicios urbanismo (PDF en web) y catálogo sede `/dossier`.
- Las licencias concedidas aparecen en el tablón como edictos cuando se publican.

## Proyectos / planeamiento

- **PGOU 1998:** mapas PDF por láminas (e1–e15) y ZIP de textos en `/es/pgou`.
- **Transparencia:** sección «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con 235 documentos (modificaciones puntuales, P15, etc.); requiere navegación AJAX Wicket (no URLs UUID estáticas en raíz).
- **ICV Inventario SU-SUZ:** 81 sectores/unidades de ejecución del municipio en WFS regional.
- **Ejemplo conocido:** Modificación Puntual UE P15 del PGOU (documentada en planifica.org y transparencia).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz`: `https://terramapas.icv.gva.es/0702_Planeamiento` (`outputFormat=GML3`, `srsName=EPSG:4326`). Filtro por `cod_ine_mun=12004` en cliente (el servidor ignora CQL parcialmente).
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
  - Mapa interactivo municipal: OpenLayers con marcador fijo; **no** expone polígonos PGOU.
- **Estrategia:** descargar 81 ámbitos SU/SUZ del inventario regional; emparejar por código de sector/UE en títulos de tablón o Drupal cuando sea posible.
- **Limitaciones:**
  - Inventario regional informativo (sin enlace a expediente del tablón).
  - Transparencia urbanismo no scrapeable sin sesión Wicket AJAX.
  - PGOU PDF sin georreferencia embebida.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Consulta de expedientes requiere login.
- `/dossier` inestable (timeout) en entorno CI.

## Adapter implementado

- `municipio.adapters.alcala_de_xivert:AlcalaDeXivertAyuntamientoAdapter`
- Fuentes: ICV WFS InventarioSuSuz + Drupal PGOU + tablón sede + páginas informativas de trámites.
