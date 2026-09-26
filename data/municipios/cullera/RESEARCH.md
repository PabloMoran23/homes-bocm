# Cullera — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web corporativa | https://www.cullera.es |
| Urbanismo | https://www.cullera.es/es/pagina/urbanismo |
| Sede electrónica | https://cullera.sedipualba.es |
| Tablón anuncios (RSS) | https://cullera.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites | https://cullera.sedipualba.es/catalogoservicios.aspx |
| Visor GIS municipal | https://cullera.gvsigonline.com/gvsigonline/core/load_public_project/UrbanismeConsultes/ |
| Transparencia ordenanzas | http://www.cullera.es/es/transparencia/ordenanzas |

## CMS y listado de expedientes

- **Web:** Drupal 10 portalesmunicipales (tema `portales`, módulos Digital Value). Sin API REST pública (`api.digitalvalue.es/cullera` devuelve `invalid id`).
- **Proyectos:** página estática `/es/pagina/urbanismo` con enlaces a PDFs (PGOU 1995 refós, modificación puntual nº55, plan parcial SUP-PRM-3-C, reparcelación sector, convenios Vega Port/Marenyet, etc.). Contenido bilingüe valenciano/castellano.
- **Tablón:** sede sedipualba (SEGEX, plataforma Dip. Albacete) con RSS funcional. Predominan anuncios administrativos (personal, subvenciones, fallas); pocos edictos urbanísticos recientes.
- **Expedientes:** no hay listado público de expedientes urbanísticos individuales; consulta vía trámite «Información urbanística» (idtramite=11176) con autenticación.

## Licencias de obra

- Catálogo sedipualba con trámites LOTU CV: obras mayores (11634), DR obras (20325), derribos (11509), desmontes (11572), parcelación (11614), licencia ambiental (11994), ocupación (11539/11552), etc.
- Sin dataset ni registro público de licencias concedidas; el adapter devuelve páginas informativas de trámites + edictos del tablón filtrados por regex.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - ICV WFS `Planeamiento.Zonificacion` (misma base URL)
  - Formato: GeoJSON (`outputFormat=application/json; subtype=geojson`, `srsName=EPSG:4326`), paginación `startIndex`
  - Filtro cliente: `cod_ine_mun=46105` (Cullera)
  - Visor municipal gvsigonline (`UrbanismeConsultes`) enlazado desde trámites sede; sin API pública de consulta por expediente
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
- **Sectores detectados (InventarioSuSuz, 44 polígonos):** NPR-5 VEGA PUERTO, PRR-12 MARENYET SUR, PRM-3 TERC-IND, JULUNA, MARENY NORTE/SUR, UE 33/1 SAN ANTONIO, etc.
- **Zonificación:** ~35 polígonos adicionales (normas subsidiarias PGOU 1995, homologaciones sectoriales).
- **Estrategia:** descargar features ICV como proyectos con polígono WGS84; enriquecer PDFs/tablon por coincidencia de tokens sectoriales (PRR-, NPR-, MARENY, VEGA, etc.)
- **Limitaciones:**
  - CQL_FILTER del WFS no funciona en servidor; requiere paginar ~12k features y filtrar por INE (lento en CI)
  - gvsigonline sin endpoint WFS/REST público para consulta puntual por código expediente
  - Licencias del tablón sin geometría explícita
  - No hay sede espublico gestiona (usa sedipualba)

## Limitaciones generales

- Sede sedipualba: trámites requieren certificado digital para presentación; sin API de expedientes públicos
- Tablón mezcla urbanismo con personal, subvenciones, fallas (filtro por regex)
- BOCM regional: DOGV (1 entrada histórica en cola)
