# La Pobla de Farnals — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (Drupal portalesmunicipales) | https://www.lapobladefarnals.es | Urbanismo, avisos, transparencia |
| Urbanismo | https://www.lapobladefarnals.es/es/pagina/urbanismo | PGOU/NNSS, edicto DRIPALIA (11.11.2016) |
| Edicto DRIPALIA (PDF) | https://www.lapobladefarnals.es/sites/www.lapobladefarnals.es/files/images/edicto_18-16_dripalia_0.pdf | Información pública proyecto DRIPALIA |
| Sede electrónica (espublico gestiona) | https://lapobladefarnals.sedelectronica.es | Trámites, tablón, transparencia |
| Tablón de anuncios | https://lapobladefarnals.sedelectronica.es/board | HTML tabla Wicket; categoría «Urbanisme» |
| Tablón urbanismo (filtro) | https://lapobladefarnals.sedelectronica.es/board/975963e4-f59b-11de-b600-00237da12c6a/ | Solo anuncios urbanísticos |
| Portal transparencia sede | https://lapobladefarnals.sedelectronica.es/transparency/75c01293-0f52-4348-958d-85c0dda000f5/ | Documentos administrativos |
| Catálogo trámites | https://lapobladefarnals.sedelectronica.es/dossier | Licencias/DR (requiere identificación para consulta) |
| ICV WFS zonificación | https://terramapas.icv.gva.es/0702_Planeamiento | Planeamiento municipal (INE 46139) |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Capa zonificación CV |

## Cómo se listan expedientes

- **Drupal:** página `/es/pagina/urbanismo` con secciones PGOU/NNSS y PDFs enlazados (edicto DRIPALIA). Sin listado dinámico de expedientes.
- **Sede espublico:** tablón `/board` con filas HTML (`class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`). En septiembre 2026 hay 1 anuncio urbanístico (licencia de ocupación costas / redes eléctricas).
- **ICV WFS:** 3 denominaciones del Plan General (expediente 20080556) con geometría poligonal.

## Licencias

- No hay dataset público de licencias concedidas.
- El tablón publica edictos puntuales (licencias de ocupación, costas).
- Trámites de licencia/DR vía sede `/dossier` (sin listado histórico público).

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:** ICV WFS `Planeamiento.Zonificacion`, filtro `cod_ine_mun=46139` (EPSG:4326 GeoJSON)
- **Instrumentos:** Plan general (exp. 20080556) con variantes: «Plan general», «PLAN GENERAL (RIESGO DE INUNDACION 6)», «PLAN GENERAL (ÁMBITO DERECHO MINERO)»
- **Estrategia:** descarga WFS por INE + matching por denominación en títulos de tablón/Drupal; enriquecimiento `geom_geojson` en proyectos ICV
- **Limitaciones:** sin visor municipal propio; tablón/PDF sin enlace GIS por expediente; licencias sin polígono salvo match textual con sector ICV
