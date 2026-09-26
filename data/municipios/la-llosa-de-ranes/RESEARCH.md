# La Llosa de Ranes — investigación portal ayuntamiento

**Municipio:** La Llosa de Ranes (Valencia, Comunitat Valenciana)  
**Slug:** `la-llosa-de-ranes`  
**INE:** 46157  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.lallosaderanes.es | Operativa — Drupal 10 portalesmunicipales.es |
| Urbanisme | https://www.lallosaderanes.es/pagina/urbanisme | Operativa — PDF edicto versión preliminar + enlaces IP |
| IP modificación PE Narengs | https://www.lallosaderanes.es/pagina/informacio-publica-modificacio-puntual-del-pla-especial-narengs | Operativa |
| IP versión preliminar PG | https://www.lallosaderanes.es/pagina/informacio-publica-versio-preliminar-del-pla-general-informe-sostenibilitat-ambiental-estudi-preliminar-del-paisatge | Operativa — índice volúmenes PDF |
| Instàncies i sol·licituds | https://www.lallosaderanes.es/pagina/instancies-sollicituds | Operativa — formularios obra/licencias |
| Anuncios web | https://www.lallosaderanes.es/listado-titulares/anuncio | Operativa — mayoría no urbanística |
| Sede electrónica | https://lallosaderanes.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://lallosaderanes.sedelectronica.es/board/ | Operativa — 1 fila en scrape (calendario fiscal) |
| Catálogo trámites | https://lallosaderanes.sedelectronica.es/dossier | Trámites licencias (sin histórico público) |
| Consulta expedientes | https://lallosaderanes.sedelectronica.es/expedientes | Requiere autenticación |

## Cómo se listan expedientes

- **Planeamiento vigente:** capa ICV GVA `InventarioSuSuz` (WFS) con 15 ámbitos SU/SUZ (sectores y UEs) para INE 46157.
- **Información pública activa:** páginas Drupal `/pagina/informacio-publica-...` (modificación PE Narengs, PG preliminar) y PDFs en `/sites/www.lallosaderanes.es/files/`.
- **Tablón sede:** espublico gestiona Wicket; en el momento del scrape solo anuncio fiscal (no urbanístico).
- **No hay** visor ArcGIS municipal ni listado HTML de expedientes en curso en la web.

## Licencias de obra

- Formularios en instàncies (`instancia-obres.pdf`, comunicación actividades, licencia ambiental).
- Sin dataset histórico de concesiones con coordenadas.
- Adapter incluye páginas informativas de trámites + tablón sede.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa `ms:InventarioSuSuz`, filtro client-side `cod_ine_mun=46157`
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
- **Estrategia:** paginación WFS (200 features/página), polígonos GML → GeoJSON WGS84; match por sector/UE en títulos de proyectos web.
- **Limitaciones:**
  - Geometría solo para instrumentos de planeamiento en inventario ICV (no licencias de obra).
  - CQL_FILTER del WFS no filtra correctamente por municipio; se filtra en cliente.
  - Tablón sede y anuncios IP recientes sin polígono enlazable.
  - Sin shapefile municipal publicado en la web.

## Limitaciones generales

- Tablón paginado Wicket (solo primera página visible).
- Consulta expedientes requiere login.
- Web en valenciano/catalán.
- Provincia en `queue.yaml` incorrecta (`La Llosa de Ranes`); manifest usa `Valencia`.

## Adapter implementado

- `municipio.adapters.la_llosa_de_ranes:LaLlosaDeRanesAyuntamientoAdapter`
- Fuentes: ICV WFS + páginas/PDFs Drupal + tablón sede + trámites informativos.
