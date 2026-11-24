# Oliva — investigación portal ayuntamiento

Municipio: **Oliva** (`oliva`) — Valencia, Comunitat Valenciana. INE `46181`. Sin boletín regional asociado en cola BOCM.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal DigitalValue) | https://www.oliva.es/ |
| PGOU / transparencia web | https://www.oliva.es/es/transparencia/plan-general-ordenacion-urbana-pgou |
| Planeamiento | https://www.oliva.es/es/pagina/planeamiento |
| Enlaces urbanísticos | https://www.oliva.es/es/pagina/enlaces-de-interes-urbanistico |
| Portal transparencia (DigitalValue) | https://transparencia.oliva.es/ |
| Sede electrónica (espublico gestiona) | https://oliva.sedelectronica.es/ |
| Tablón de anuncios | https://oliva.sedelectronica.es/board |
| Catálogo trámites | https://oliva.sedelectronica.es/dossier |
| Transparencia sede (sección 6) | https://oliva.sedelectronica.es/transparency |
| ICV / visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion |
| Visor municipal (Oliva Oberta, referencia) | http://www.olivaoberta.es/va/visor |
| QGIS Cloud SIG (legacy, vella.oliva.es) | https://qgiscloud.com/ciudaddeoliva/SIG_OLIVA_WEB/ |

## Expedientes / planeamiento

- **ICV GVA WFS:** capa `Planeamiento.Zonificacion`, filtro client-side `cod_ine_mun=46181` — ~22 instrumentos únicos (PGOU, sectores Aigua Blanca, Oliva Nova, almacenes, etc.).
- **Web oliva.es:** Drupal con PDFs de normas PGOU (NORM-PL*, NORM-BV*, etc.), modificaciones recientes (criterios interpretativos sectores 6/19, altillos) y páginas de planeamiento / mapas temáticos (p. ej. sector 15).
- **Transparencia DigitalValue:** sección Urbanisme con PGOU y planes parciales; API `api.digitalvalue.es/oliva` (sin scrape en adapter; semillas HTML/PDF estáticas).
- **Tablón /board:** tabla Wicket espublico (~10 filas visibles); en muestra nov-2026 predominan anuncios administrativos (personal, pleno, DANA); filtro urbanístico vía regex en adapter.
- **Consulta expedientes:** carpeta ciudadana en sede — requiere certificado / DNIe.

## Licencias

- No hay dataset público de licencias concedidas con coordenadas.
- Trámite «Sol·licitud de llicència o autorització urbanística» vía catálogo sede (`/dossier`); histórico no publicado en abierto.
- Adapter incluye páginas informativas: tablón, dossier y enlaces urbanísticos.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `Planeamiento.Zonificacion`, `cod_ine_mun=46181` (~65 polígonos GML, 22 instrumentos). Salida GML3 → GeoJSON WGS84 en adapter.
  - Visor GVA / cartoweb CMA (enlaces en web municipal); visor QGIS Cloud municipal (legacy, sin API REST estable).
  - Sin ArcGIS MapServer municipal con query por expediente de licencia.
- **Estrategia:** filas base desde ICV WFS; matching por keywords (Plan general, Residencial-2, sector) contra polígonos; enriquecimiento tablón cuando aparezcan edictos urbanísticos.
- **Limitaciones:** zonificación agregada por instrumento de planeamiento, no geometría por expediente de licencia; tablón sin paginación Wicket AJAX; visor SIG municipal desactualizado (2017 en web legacy).

## Limitaciones generales

- Sede espublico: `insecure_ssl: true` por consistencia con otros adapters espublico.
- Tablón: solo primera página HTML.
- Sin re-parse BOCM en este adapter (`bocm_count: 0` en cola).
