# Rocafort — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `rocafort` |
| INE municipio | 46216 |
| CCAA | Comunitat Valenciana (DOGV) |
| Web | https://www.rocafort.es |
| Sede | https://rocafort.sede.dival.es (Dival / Sedipualba) |

## URLs base y semillas

- **Web municipal (Drupal 10 / portalesmunicipales):** https://www.rocafort.es
- **Transparencia — información urbanística:** https://www.rocafort.es/es/transparencia/informacion-urbanistica (PGOU, modificaciones 9–12, normativa, PDFs)
- **Planeamiento municipal:** https://www.rocafort.es/es/pagina/planeamiento-municipal (catálogo de protecciones, documentación PGOU en PDF)
- **Instancias medio ambiente y urbanismo:** https://www.rocafort.es/es/pagina/instancias-medio-ambiente-urbanismo
- **Sede — tablón RSS:** https://rocafort.sede.dival.es/tablondeanuncios/tablon_rss.aspx
- **Sede — catálogo Urbanismo (área 1936):** https://rocafort.sede.dival.es/catalogoservicios.aspx?area=1936 (sin procedimientos listados en HTML)
- **Registro GVA planeamiento:** https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46216%20ROCAFORT/1%20P.%20GENERAL/

## Expedientes / planeamiento

- **Listado:** principalmente **PDFs estáticos** en Drupal (transparencia y planeamiento) y **índice de carpetas** en el registro GVA (modificaciones PGOU históricas).
- **Tablón electrónico:** RSS ASP.NET con títulos y enlaces `anuncio.aspx?id=…`; en la muestra reciente predominan edictos administrativos (empleo, IAE), no expedientes urbanísticos.
- **No** hay visor de expedientes IP ni API JSON pública en la sede.

## Licencias de obra

- **No** hay listado público de licencias concedidas (coordenadas, parcela, etc.).
- Documentación informativa: modelo PDF de licencia urbanística en la web municipal.
- Catálogo de trámites de Urbanismo en sede vacío; licencias vía instancia presencial/electrónica sin publicación de concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `https://terramapas.icv.gva.es/0702_Planeamiento` capa `ms:InventarioSuSuz`, filtro `cod_ine_mun=46216` (6 sectores SU/SUZ con polígono).
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
- **Estrategia:** ingestar sectores del inventario ICV como filas de `proyectos.jsonl` con `geom_geojson`; intentar enriquecer anuncios/PDFs por coincidencia de tokens UE/SD en título.
- **Limitaciones:** licencias y expedientes del tablón/PDF **no** enlazan geometría por expediente; WFS no admite CQL fiable en este servicio (paginación global + filtro cliente por INE).

## Limitaciones técnicas

- Tablón RSS en `iso-8859-1`.
- Governalia no desplegado para Rocafort (redirección genérica).
- Paginación ICV WFS ~12k features por consulta (latencia ~2 min en backfill completo).
