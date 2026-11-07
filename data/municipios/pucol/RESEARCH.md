# Investigación — Puçol (`pucol`)

## Fuentes del portal

| Recurso | URL | Estado |
|---------|-----|--------|
| Web municipal | https://www.pucol.es | Drupal 10 Digital Value (portalesmunicipales) |
| Instancias / modelos urbanismo | https://www.pucol.es/es/pagina/instancias | PDFs `urb_*`, `URB06`, `URB11` |
| Departamentos | https://www.pucol.es/es/pagina/departamentos-del-ayuntamiento-de-pucol | contacto `urbanismo@pucol.es` |
| Sede electrónica | https://pucol.sede.dival.es | Sedipualba / Dival ASP.NET |
| Tablón de anuncios | https://pucol.sede.dival.es/tablondeanuncios/ | Operativo |
| Tablón RSS | https://pucol.sede.dival.es/tablondeanuncios/tablon_rss.aspx | ISO-8859-1, ~15 ítems recientes |
| Catálogo urbanismo | https://pucol.sede.dival.es/catalogoservicios.aspx?area=1156 | DR, licencias, certificados urbanísticos |
| Transparencia | https://transparencia.pucol.es/ | Portal separado |
| Archivo histórico urbanismo | https://archivo.xn--puol-1oa.es/.../urbanismo | PDFs PGOU, PAI, sectores (legacy) |

## Listado de expedientes / proyectos

- **Tablón RSS:** edictos de información pública y actuaciones (p. ej. expediente vegetación dunar); filtrado por regex urbanismo.
- **Drupal:** PDFs de planeamiento en instancias y enlaces en departamentos (sin visor de expedientes IP enlazado).
- **GVA registro:** índice Apache `46205 PUZOL` con carpetas P. GENERAL y P. DIFERIDO.

## Licencias

- No hay dataset público de licencias concedidas.
- Trámites en sede (declaraciones responsables, licencia obra mayor `idtramite=10215`, etc.) y modelos PDF en la web.
- El adapter expone trámites informativos + edictos del tablón con palabras clave de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `ms:InventarioSuSuz` (`https://terramapas.icv.gva.es/0702_Planeamiento`), filtro cliente `cod_ine_mun=46205` (PUZOL).
  - Polígonos SU/SUZ por sector (campo `pp`, `ue`); sin vínculo directo expediente-tablero.
  - Planos PDF en web/GVA sin georreferenciación automática.
- **Estrategia:** ingestar sectores WFS como proyectos con `geom_geojson`; cruzar títulos del tablón/PDF con tokens de sector (UE-, sector, etc.).
- **Limitaciones:** sin visor municipal ArcGIS; expedientes del tablón no traen geometría propia; coordenadas EPSG:4326 vía WFS paginado.

## Limitaciones generales

- RSS en latin-1; paginación WFS hasta ~12k features globales (filtro INE en cliente).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
