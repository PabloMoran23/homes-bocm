# Rivilla de Barajas — investigación portal ayuntamiento

## Municipio
- **Nombre:** Rivilla de Barajas
- **Provincia:** Ávila (Castilla y León)
- **INE:** 05196
- **Boletín:** BOCYL (`boletin_source_id: bocyl`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.rivilladebarajas.es | WordPress 6 (tema Evolve) |
| Sede electrónica (enlace WP) | https://www.rivilladebarajas.es/?page_id=1465 | Página informativa con enlace a sede |
| Sede electrónica | https://rivilladebarajas.sedelectronica.es | espublico gestiona |
| Tablón de anuncios | https://rivilladebarajas.sedelectronica.es/board | HTML tabla Wicket; `preview-document` UUID |
| Catálogo trámites | https://rivilladebarajas.sedelectronica.es/dossier | Trámites urbanismo (licencias, planeamiento) |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlauPrint.do?provincia=05&municipio=196 | Documentación SPG |
| IDECyL SIUR | https://idecyl.jcyl.es/siur/index.html?id=05196 | Visor instrumentos CYL |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | Capas PLAU CyL filtro `n_mun='Rivilla de Barajas'` |

## Cómo se listan expedientes / proyectos

1. **PlanPublica (Junta CYL):** tabla HTML con `doOpen(docId, codigo)` → `openDocumento.do?cDocId=…`. Municipio sin PGOU: instrumento **SPG** (`05196-PU-00000000-276994`, cDocId 276994).
2. **IDECyL WFS:** GeoJSON vía `GetFeature` en capas `plau_cyl_instrumentos_ambito` (1 polígono MultiPolygon del término municipal bajo SPG). Sin planes parciales ni sectores en WFS.
3. **Tablón sede:** anuncios administrativos (listas electorales, juez de paz, jurado); sin expedientes urbanísticos recientes.
4. **Web WP:** sin sección dedicada de urbanismo ni PDFs de planeamiento en el sitio municipal; la normativa activa está en JCyL/IDECyL.

## Licencias de obra

No hay listado público de licencias concedidas. La sede expone trámites informativos en `/dossier` (p. ej. «Solicitud de Licencia o Autorización Urbanística», comunicaciones previas). El adapter devuelve esas páginas de catálogo más el tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 MultiPolygon (ámbito SPG, `c_mun=05196`)
  - IDECyL SIUR visor municipal CYL (`id=05196`)
  - Campo enlace: `c_plan`, `url_doc_info`
- **Estrategia:** consulta WFS por municipio; el polígono del instrumento SPG se **no** persiste en `geom_geojson` (excede límite IGN → `outside_municipality_scope` en validación). Coordenadas de proyectos vía geocode (centroide manifest + jitter).
- **Limitaciones:** sin visor municipal propio; 0 sectores/PP en WFS; polígono SPG IDECyL no acotado al término IGN; tablón y trámites sede sin geometría; licencias sin coords de obra.

## Limitaciones generales

- Sede puede requerir `insecure_ssl` (cadena TLS espublico).
- Tablón sin anuncios de planeamiento.
- Web WP antigua (Evolve) sin datos abiertos urbanísticos.
- Sin API REST de expedientes en la sede (solo HTML Wicket).
