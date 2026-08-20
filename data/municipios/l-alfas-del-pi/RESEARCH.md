# L'Alfàs del Pi — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `l-alfas-del-pi` |
| INE | 03009 |
| Provincia | Alicante |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## Fuentes

### Web municipal (WordPress Divi)

- Base: https://www.lalfas.es
- Urbanismo: https://www.lalfas.es/servicios/urbanismo/
- PGOU (VSP): https://www.lalfas.es/servicios/urbanismo/pgou-vsp/
- Tablón de anuncios: https://www.lalfas.es/list-transparencia/tablon-de-anuncios/
- WP REST: `/wp-json/wp/v2/search?search=...`

### Sede electrónica (Maggioli PortalCiudadania)

- Base: https://ciudadano.lalfas.es/PortalCiudadania/
- SPA; trámites requieren identificación; sin listado público scrapeable

### ICV / GVA — planeamiento

- WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
- TypeName: `ms:Planeamiento.Zonificacion`, `cod_ine_mun=03009`

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV WFS zonificación (`cod_ine_mun=03009`); visor GVA
- **Estrategia:** WFS 2.0 GML3 EPSG:4326; matching título↔`denominaci`/`expediente`
- **Limitaciones:** zonificación PGOU, no parcela; sede SPA sin API
