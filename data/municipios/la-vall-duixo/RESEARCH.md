# La Vall d'Uixó — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `la-vall-duixo` |
| INE | 12126 |
| Provincia | Castellón / Comunitat Valenciana |
| Boletín | DOGV (`dogv`, 2 entradas BOCM) |

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.lavallduixo.es | Drupal (sites/L01121264) |
| Sede electrónica | https://sede.lavallduixo.es | STA/TAO T-Systems |
| Tablón de anuncios | https://sede.lavallduixo.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | JSON embebido `dataset_PTS2_TABLON` |
| Catálogo trámites | https://sede.lavallduixo.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | Urbanismo: keyword `PTS_PC_004` |
| Planeamiento | https://www.lavallduixo.es/es/planeamiento-urbanistico | PGOU, planes parciales, PMUS |
| Exposición al público | https://www.lavallduixo.es/es/exposicion-al-publico | Modificaciones puntuales recientes (PDF) |
| Portal transparencia | https://www.lavallduixo.es/es/portal-transparencia | Sin listado urbanístico estructurado |

## Cómo se listan expedientes / proyectos

1. **Web Drupal:** páginas de planeamiento con enlaces a PDFs en `/sites/L01121264/files/` (PGOU, planes parciales por sector/área, PMUS).
2. **Exposición al público:** modificaciones puntuales recientes (p. ej. Sector 11, Sector 9-A).
3. **Sede STA tablón:** 67 anuncios en `dataset_PTS2_TABLON` (mayoría no urbanística: empleo, tributos).
4. **Catálogo STA:** ~40 trámites de Urbanismo y Vivienda (`PTS_PC_004`): licencias, certificados, programas de actuación.
5. **ICV WFS InventarioSuSuz:** 31 sectores SU/SUZ aprobados con polígonos para INE 12126.

## Cómo se publican licencias

- No hay listado histórico público de licencias concedidas en la web municipal.
- El tablón sede publica edictos puntuales; en la investigación no había licencias de obra activas.
- Trámites de licencia vía catálogo STA: Licencia de Edificación-Obra Mayor, Obra Menor, Declaración Responsable de Obras, etc.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento/ows`
  - Parámetros: `outputFormat=GML3`, `srsName=EPSG:4326`, paginación `STARTINDEX`/`count=200`
  - Filtro en cliente: `cod_ine_mun=12126` (31 features con polígono)
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
- **Estrategia:** descargar WFS paginado, convertir `posList` GML → GeoJSON Polygon WGS84; enriquecer filas Drupal/tablón por coincidencia de sector/UE en título.
- **Limitaciones:**
  - WFS no admite `application/json`; solo GML3.
  - No hay visor municipal ArcGIS enlazable a expedientes individuales.
  - PDFs de planes parciales no están georreferenciados.
  - Tablón STA sin geometría; licencias son trámites informativos o edictos PDF.

## Limitaciones generales

- Sede STA puede requerir `sede_insecure_ssl: true` en algunos entornos.
- Tablón actual mayoritariamente no urbanístico.
- Catálogo STA lista trámites, no concesiones históricas.

## Adapter

- `municipio.adapters.la_vall_duixo:LaVallDuixoAyuntamientoAdapter`
- Fuentes: ICV WFS + Drupal planeamiento PDFs + tablón STA + catálogo urbanismo + páginas informativas licencias.
