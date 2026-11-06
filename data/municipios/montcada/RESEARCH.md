# Moncada (València) — portal y fuentes urbanísticas

## URLs base y páginas semilla

| Rol | URL |
|-----|-----|
| Web corporativa (Drupal) | https://www.moncada.es |
| Urbanismo | https://www.moncada.es/es/pagina/urbanismo |
| Planeamiento vigente y en tramitación (PDFs) | https://www.moncada.es/es/pagina/planeamiento-vigente-tramitacion |
| PGOU (transparencia Digital Value) | http://transparencia.moncada.es/es/transparencia/plan-general-de-ordenacion-urbana-pgou |
| Sede electrónica (Sedipualba) | https://moncada.sedipualba.es |
| Tablón — RSS | https://moncada.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites — área Urbanisme | https://moncada.sedipualba.es/catalogoservicios.aspx?area=1139&ambito=1 |
| Punto integrado urbanismo (info de contacto) | https://www.moncada.es/es/seccion-punto-integrado-informacion-para-tramitacion-gestion-expedientes-urbanisticos |

**Visor presupuestario** en `http://visor.moncada.es` no es visor urbanístico (solo presupuesto municipal).

## Cómo se listan expedientes y anuncios

- **Tablón de anuncios (sede):** HTML ASP.NET con filtro por área «Urbanisme i planejament» (valor `836` en el formulario). **RSS** del tablón (~20 ítems) sirve de señal rápida; el listado HTML tiene paginación «Pàgina X de Y» que en pruebas no varió el conjunto de filas vía POST simple (posible autopostback JS); el adaptador prioriza **WFS + web + RSS** sin depender de paginar el tablón.
- **Trámites:** catálogo filtrado por área 1139 (ej. comunicación de obras DR, registro S771, denuncia urbanística).
- **Planeamiento en web:** páginas Drupal con enlaces a **PDF** (planes parciales, estudios de detalle, etc.), sin listado JSON público.

## Licencias de obra

No hay **registro abierto de concesiones** con fecha de otorgamiento en el portal analizado. Se exponen **fichas de trámites** (comunicación de obras vinculada a declaración responsable, etc.). El pipeline exporta esas filas como trámites informativos cuando la política de entidades lo permite.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** [WFS Generalitat — Inventario SU/SUZ](https://terramapas.icv.gva.es/0702_Planeamiento) (`ms:InventarioSuSuz`), filtrado en cliente por `cod_ine_mun` **46171**; visor estatal de referencia: [visor.gva.es](https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz) (capa SU/SUZ).
- **Estrategia:** descarga paginada WFS `GetFeature` (GML3, `srsName=EPSG:4326`), polígonos `gml:Polygon` → GeoJSON; enriquecimiento cruzado por tokens UE/PP/PRI en títulos de anuncios y PDFs cuando aplica.
- **Limitaciones:** geometría **por sector SU/SUZ**, no por expediente concreto; anuncios del tablón suelen ser **PDF/HTML sin enlace GIS**; el PGOU en transparencia es contenido editorial sin servicio mapa embebido en esta integración.
