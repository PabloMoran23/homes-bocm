# Paiporta — investigación portal ayuntamiento

**Municipio:** Paiporta (Valencia, Comunitat Valenciana)  
**INE oficial:** `46188` · **ICV WFS `cod_ine_mun`:** `46186` (escudo sede `46186.png`)  
**DOGV:** 1 entrada (`dogv`)

## URLs base y páginas semilla

| Rol | URL |
|-----|-----|
| Web corporativa | https://www.paiporta.es |
| Urbanismo (Drupal) | https://www.paiporta.es/es/pagina/urbanismo-obras-publicas-territorio |
| Exposición pública | https://www.paiporta.es/es/pagina/exposicion-publica |
| Sede electrónica | https://paiporta.sedipualba.es |
| Tablón anuncios | https://paiporta.sedipualba.es/tablondeanuncios/default.aspx |
| Tablón RSS | https://paiporta.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo Urbanismo (área 959) | https://paiporta.sedipualba.es/catalogoservicios.aspx?area=959&ambito=1 |

## Tecnología

- **paiporta.es:** Drupal (paths `/es/pagina/…`, documentos en `/sites/www.paiporta.es/files/Recursos/Documentos/Urbanismo/`).
- **paiporta.sedipualba.es:** ASP.NET WebForms (Sedipualba / Diputación de Albacete). Tablón + catálogo de trámites + CSV en PDFs.

## Proyectos / expedientes urbanísticos

1. **ICV InventarioSuSuz** — sectores y unidades de ejecución aprobados (PD-1, PD-2, SECTOR UE 12, etc.) con polígono WFS.
2. **Web Drupal** — secciones PGOU, planes de desarrollo, exposición pública, edictos PDF (p. ej. modificación plan nº 23).
3. **Tablón sedipualba** — edictos varios; el RSS reciente está dominado por RRHH/festividades; filtro por palabras clave urbanísticas.

**No hay** visor municipal de expedientes ni API JSON de planeamiento.

### Cómo se listan

- **Drupal:** páginas estáticas + enlaces PDF.
- **Tablón:** RSS 2.0 (ISO-8859-1) + listado HTML `anuncio.aspx?id=…`.
- **ICV:** WFS GML3 paginado (`STARTINDEX`), filtro cliente `cod_ine_mun=46186`.

## Licencias de obra

- **No hay** registro público de licencias concedidas.
- **Catálogo sede:** fichas URB003 (licencia edificación), URB004 (DR obras), URB005 (1ª ocupación), etc.
- **Tablón:** edictos puntuales si se publican (LAM/LIC); mayoría de anuncios no urbanísticos en ventana RSS.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` — `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
  - ~17 polígonos Paiporta (sectores UE, PD-1/2, unidades de ejecución)
- **Estrategia:** ingestar sectores ICV con `geom_geojson`; enriquecer tablón/web por tokens sector (UE, PD, SECTOR).
- **Limitaciones:**
  - Tablón y PDFs Drupal sin geometría enlazada.
  - CQL server-side en ICV no fiable; filtro por `cod_ine_mun` en cliente (paginación lenta).
  - `www.paiporta.es` HTTPS: timeout desde entorno cloud agent (TLS handshake OK, sin respuesta); HTTP también timeout. Sede sedipualba accesible.

## Limitaciones generales

- Dominio `paiporta.org` no es el ayuntamiento (WordPress ajeno).
- `paiporta.sedelectronica.es` redirige a selector genérico sin sede activa.
- Índice GVA `46188 PAIPORTA` en mediambient.gva.es no encontrado (404).
- Sync Supabase requiere `SUPABASE_DB_URL` en CI/local.
