# Picassent — investigación portal ayuntamiento

**Municipio:** Picassent (Valencia, Comunitat Valenciana)  
**INE:** `46194`  
**BOCM/DOGV:** 3 entradas (`dogv`)

## URLs base y páginas semilla

| Rol | URL |
|-----|-----|
| Web corporativa | https://www.picassent.es |
| Sede electrónica | https://picassent.sedipualba.es |
| Transparencia / planeamiento | https://picassent.governalia.es/es/transparencia/planes-urbanisticos-y-estudios-de-impacto-ambiental/ |
| Tablón anuncios | https://picassent.sedipualba.es/tablondeanuncios/default.aspx |
| Tablón RSS | https://picassent.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites URB | https://picassent.sedipualba.es/catalogoservicios.aspx?ambito=1&area=1635 |
| Formularios urbanismo | https://picassent.governalia.es/impresos-y-formularios/ |
| Registro planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46194%20PICASSENT/ |

## Tecnología

- **picassent.es:** Drupal 10 + Digital Value (`portalesmunicipales.es`).
- **picassent.sedipualba.es:** ASP.NET WebForms (Diputación de Albacete). Tablón + trámites + PDFs vía `documento.aspx`.
- **picassent.governalia.es:** WordPress (Governalia). PDFs de planeamiento en `/wp-content/uploads/sites/35/`.

## Proyectos / expedientes urbanísticos

1. **Governalia transparencia** — catálogo principal: PGOU (1996), modificaciones, planes parciales (SUZI-2, SUZT-1, VERTIX XXI…), PRI, estudios de detalle. Acordeón HTML + enlaces PDF directos.
2. **Tablón sedipualba** — edictos de exposición pública (expedientes `Exp NN/YY LAM`), fotovoltaica, etc. PDFs vía `documento.aspx?id=…&modo=abrir`.
3. **GVA mediambient** — índice de instrumentos aprobados (`46194-1000 PLAN GENERAL 1996…`).
4. **picassent.es/proyectos-urbanismo** — obra pública / licitaciones (no instrumental PGOU).

**No hay** registro público de expedientes ni visor municipal de expedientes.

### Cómo se listan

- **Governalia:** secciones `<h2 class="wp-block-heading">` + enlaces PDF.
- **Tablón:** RSS 2.0 (ISO-8859-1) con `<item><title>…</title><link>anuncio.aspx?id=…</link>`.
- **GVA:** listado Apache de carpetas con subdirectorios por instrumento.

## Licencias de obra

- **No hay** listado público de licencias concedidas.
- **Tablón:** edictos LAM (`Exp 47/25 LAM`, `Exp 22/25 LAM`) = licencias/actividades en exposición pública.
- **Catálogo sedipualba:** fichas informativas (DR obra, fotovoltaica, informes urbanísticos, ocupación vía pública).
- **Formularios PDF:** governalia (L-SU-1, DR-SU-3, etc.) — plantillas, no concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Filtro cliente `cod_ine_mun=46194` (20 polígonos: SUZR-3, SUZR-5, SUZR-6 UE-4, etc.)
  - GML3, paginación `STARTINDEX`, `srsName=EPSG:4326`
- **Estrategia:** ingestar sectores ICV con `geom_geojson`; enriquecer edictos tablón/governalia por coincidencia de tokens sector (SUZR, UE-…).
- **Limitaciones:**
  - Tablón y PDFs governalia sin geometría enlazada.
  - Sin visor municipal ArcGIS ni WFS propio.
  - CQL server-side en ICV no fiable; filtro por `cod_ine_mun` en cliente.

## Limitaciones generales

- Sede sedipualba sin registro de concesiones de licencias.
- Tablón RSS en ISO-8859-1.
- Filtro área Urbanismo en tablón requiere POST (`__doPostBack`); se usa RSS + filtro por título.
- `picassent.es/proyectos-urbanismo` es obra pública, no planeamiento instrumental.
