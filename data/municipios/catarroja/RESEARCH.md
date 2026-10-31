# Catarroja — investigación portal ayuntamiento

**Municipio:** Catarroja (Valencia, Comunitat Valenciana)  
**INE:** `46094`  
**BOCM:** sin boletín asociado en cola

## URLs base y páginas semilla

| Rol | URL |
|-----|-----|
| Web corporativa | https://www.catarroja.es |
| Urbanismo | https://www.catarroja.es/es/urbanismo |
| Transparencia / PGOU | https://www.catarroja.es/es/transparencia/instrumentos-planeamiento-urbanistico |
| Sede electrónica | https://catarroja.sedipualba.es |
| Tablón anuncios | https://catarroja.sedipualba.es/tablondeanuncios/default.aspx |
| Tablón RSS | https://catarroja.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites urbanismo | https://catarroja.sedipualba.es/catalogoservicios.aspx?area=1254&ambito=1 |
| Registro planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46094%20CATARROJA/ |
| Visor PGE (Geoinnova) | https://pgecatarroja.geoinnova.org/ |

## Tecnología

- **catarroja.es:** Drupal 10 + Digital Value (`portalesmunicipales.es`, Matomo site 259).
- **catarroja.sedipualba.es:** ASP.NET WebForms (Diputación de Albacete). Tablón + trámites + PDFs vía `documento.aspx` / `anuncio.aspx`.
- **pgecatarroja.geoinnova.org:** visor participación PGOU (Leaflet); sin API pública de geometría por expediente.

## Proyectos / expedientes urbanísticos

1. **Transparencia Drupal** — instrumentos PGOU en `/files/documents/Economica/PGOU/` (memoria, anexos cartográficos PDF).
2. **Tablón sedipualba** — edictos (p. ej. «Edicto Información Pública»), convocatorias; PDFs en `anuncio.aspx?id=…`.
3. **GVA mediambient** — índice Apache de instrumentos aprobados (`46094 …`).
4. **Visor PGE Geoinnova** — consulta ciudadana del proceso PGOU; no enlaza expedientes urbanísticos individuales.

**No hay** registro público consultable de expedientes de planeamiento por número/código.

### Cómo se listan

- **Drupal:** enlaces a PDFs en página de transparencia; sección urbanismo con enlace a sede.
- **Tablón:** RSS 2.0 (ISO-8859-1) con `<item><title>…</title><link>anuncio.aspx?id=…</link>`.
- **GVA:** listado de carpetas por instrumento.

## Licencias de obra

- **No hay** listado público de licencias concedidas (fecha/dirección).
- **Catálogo sedipualba (área 1254):** fichas informativas — Llicència d'Obra Major (`idtramite=13448`), Declaració responsable d'Obra (`13913`), primera ocupación, compatibilidad urbanística, etc.
- **Tablón:** edictos ocasionales de licencias/actividades si aparecen en título (filtro por regex).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Filtro cliente `cod_ine_mun=46094` (sectores SU/SUZ del municipio)
  - GML3 paginado (`STARTINDEX`), `srsName=EPSG:4326` — barrido lento; en CI `wfs_max_startindex: 0`
  - Visor PGE Geoinnova: mapa de participación PGOU, sin WFS/ArcGIS REST público enlazado a expedientes
- **Estrategia:** ingestar polígonos ICV con `geom_geojson` (WFS paginado + filtro cliente `cod_ine_mun=46094`; el `CQL_FILTER` del servicio no filtra bien en `STARTINDEX>0`).
- **Limitaciones:**
  - Tablón y PDFs transparencia sin geometría enlazada.
  - Visor municipal Geoinnova no expone query por expediente.

## Limitaciones generales

- Sede sedipualba sin registro de concesiones de licencias.
- Tablón RSS en ISO-8859-1.
- Consulta de estado de expediente solo presencial/OIAC o área privada sede (certificado).
- Email urbanismo: urbanisme@catarroja.es
