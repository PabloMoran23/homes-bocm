# Requena — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal 10) | https://www.requena.es |
| Urbanismo | https://www.requena.es/pagina/urbanismo-4 |
| Tablón edictos urbanismo | https://www.requena.es/pagina/tablon-edictos-urbanismo |
| PGOU | https://www.requena.es/pagina/plan-general-ordenacion-urbana |
| Sede electrónica (sedipualba) | https://requena.sedipualba.es |
| Tablón RSS sede | https://requena.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites | https://requena.sedipualba.es/catalogoservicios.aspx |

## Proyectos / planeamiento

- **Tablón edictos urbanismo (Drupal):** listado estático de PDFs/ZIP en `/sites/www.requena.es/files/Departamentos/urbanismo/` (PRI UE, modificaciones PGOU, convenios, información pública, actuaciones aisladas).
- **ICV terramapas:** capa WFS `ms:InventarioSuSuz` con polígonos de sectores SU/SUZ del municipio (`cod_ine_mun=46215`, 7 unidades en inventario).
- **Tablón sede:** RSS general; filtro por palabras clave urbanísticas para edictos puntuales (la mayoría son administrativos).

Formato: HTML + enlaces directos a documentos; no hay API JSON de expedientes.

## Licencias de obra

- No hay listado público de concesiones con coordenadas.
- Trámites informativos en sedipualba (licencias de espectáculos, etc.) y edictos en tablón RSS cuando mencionan licencias/obras.
- El adapter expone páginas informativas del tablón y trámites de licencia del catálogo (sin fechas de concesión).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV WFS `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `ms:InventarioSuSuz`, campos `pp`, `ue`, `clasificacion`, geometría GML → GeoJSON WGS84.
- **Estrategia:** ingestar sectores del inventario SU/SUZ por `cod_ine_mun`; enriquecer edictos del tablón Drupal que citan códigos UE/PRI (p. ej. `pri_ue_c10`) vía matching textual contra inventario WFS.
- **Limitaciones:** CQL_FILTER en el WFS no filtra en servidor (se pagina y filtra en cliente). Los polígonos `InventarioSuSuz` con `cod_ine_mun=46215` aparecen ~39.19°N/-0.34°W (fuera del término IGN de Requena ~39.49°N/-1.10°W); el adapter descarta esas geometrías. Expedientes de licencia del tablón no traen polígono propio.

## Otras limitaciones

- Boletín DOGV: 1 aviso histórico en BOCM regional (no re-parseado).
- Sede sedipualba sin área URB dedicada en catálogo (trámites dispersos).
- Provincia en `queue.yaml` aparece como «Requena»; INE provincia es Valencia (462).
