# Cieza — investigación portal ayuntamiento

Municipio: **Cieza** (`cieza`), provincia Murcia, CCAA `murcia`. Código INE municipio: **30019**. Sin boletín BOCM asociado en cola.

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Sede electrónica (Sedipualba) | https://cieza.sedipualba.es | ASP.NET, fuente principal |
| Tablón de anuncios | https://cieza.sedipualba.es/tablondeanuncios/ | Listado + filtros por área |
| Tablón RSS | https://cieza.sedipualba.es/tablondeanuncios/tablon_rss.aspx | ISO-8859-1, ~20 ítems recientes |
| Catálogo trámites | https://cieza.sedipualba.es/catalogoservicios.aspx | Por área |
| Planeamiento y Gestión Urbanística | https://cieza.sedipualba.es/catalogoservicios.aspx?area=1159&ambito=1 | Área sede 1159 |
| Obras, Vivienda e Infraestructuras | https://cieza.sedipualba.es/catalogoservicios.aspx?area=1147&ambito=1 | OVP, instancia general, etc. |
| Transparencia sede | https://cieza.sedipualba.es/transparencia/ | Documentación administrativa |
| Web corporativa | https://www.cieza.es | **Inaccesible** (timeout) desde entorno cloud agent |

### Áreas tablón (ddlArea)

- `433` — Planeamiento y Gestión Urbanística  
- `428` — Obras, Vivienda e Infraestructuras  

## Expedientes / planeamiento

- **Tablón:** anuncios en HTML (`anuncio.aspx?id=…`) y RSS; documentos adjuntos en `documento.aspx?id=…`. No hay visor de expedientes urbanísticos enlazado por código.
- **Catálogo:** trámites informativos (instancia general, OVP); no listado histórico de expedientes abiertos.
- **Acuerdos pleno:** aparecen como «Extracto Acuerdos Adoptados Junta Gobierno Local» en tablón (contenido mixto; filtro por regex urbanismo).

## Licencias de obra

- Publicación vía **tablón** (edictos) cuando existen; en la muestra RSS reciente predominan RRHH/contratación.
- **Catálogo** área Obras: trámites de ocupación vía pública y formularios; sin registro público de concesiones emitidas.
- Adapter incluye páginas informativas del tablón y catálogo (paridad mínima como otros municipios Sedipualba).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer CARM: `https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs`
  - Capa: `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo`
  - Filtro: `CQL_FILTER=Municipio='Cieza'`
  - Campos útiles: `Ambito`, `Clasificacion`; geometría MultiPolygon EPSG:4326 (~348 features, deduplicadas por ámbito en adapter).
- **Estrategia:** filas de proyecto desde polígonos WFS; enriquecimiento de tablón si el título menciona códigos de ámbito (APR*, SUNS*, UA, etc.).
- **Limitaciones:** no hay join expediente↔polígono en sede; web municipal caída/inaccesible; tablón mayoritariamente no urbanístico en RSS reciente; geometría es clasificación de suelo, no delimitación de licencia concreta.

## Limitaciones técnicas

- `www.cieza.es`: sin respuesta HTTP en pruebas (30s timeout).
- Tablón Sedipualba: paginación ASP.NET; búsqueda GET `?buscar=` no filtra de forma fiable.
- Sin API JSON de expedientes; scrape determinista RSS + HTML + WFS.

## Referencias de implementación

- Patrón sede: `municipio/adapters/sagunt.py`, `municipio/adapters/pinoso.py`
- WFS Murcia: `municipio/adapters/lorca.py` (`plu_ze_37_mun_uso_suelo`)
