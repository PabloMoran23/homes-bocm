# Cubillos del Sil — investigación portal ayuntamiento

**Municipio:** Cubillos del Sil (Castilla y León, León)  
**Fecha:** 2026-08-09

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://aytocubillosdelsil.com | Portal activo (tema municipal + GTranslate) |
| Urbanismo | https://aytocubillosdelsil.com/urbanismo/ | Enlaces a trámites y declaraciones responsables |
| Fomento y Urbanismo | https://aytocubillosdelsil.com/709-2/ | Área municipal, enlace a clasificación del suelo |
| Clasificación del suelo | https://aytocubillosdelsil.com/clasificacion-del-suelo-urbano/ | Planos PDF por núcleo (Cubillos, Cubillinos, Finolledo, Fresnedo, Cabañas de la Dornilla) + memoria NUM |
| Solicitud licencia obras mayores | https://aytocubillosdelsil.com/solicitud-de-licencia-urbanistica-de-obras-mayores/ | Formulario PDF |
| Declaración responsable obras menores | https://aytocubillosdelsil.com/declaracion-responsable-urbanistica-de-obras-menores/ | Formulario PDF |
| Prórroga licencia | https://aytocubillosdelsil.com/prorroga-de-licencia-de-obras/ | Formulario PDF |
| Anuncios y bandos | https://aytocubillosdelsil.com/ayuntamiento/anuncios/ | Anuncios municipales (WP) |
| Sede electrónica (espublico gestiona) | https://cubillosdelsil.sedelectronica.es/board | Tablón de anuncios (~10 filas visibles) |
| Transparencia sede | https://cubillosdelsil.sedelectronica.es/transparency | Bloque «Urbanismo, obras públicas y medio ambiente» (4 docs) |
| Archivo PLAU JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=064 | Planeamiento aprobado (c_mun 24064) |
| WP REST API | https://aytocubillosdelsil.com/wp-json/wp/v2 | pages + posts |

## Cómo se listan expedientes

- **WordPress:** páginas estáticas con PDFs de planeamiento en `/wp-content/uploads/`. REST API `wp/v2/pages` y `wp/v2/posts`.
- **Clasificación del suelo:** listado manual de planos PDF por núcleo de población y memoria de Normas Urbanísticas Municipales (NUM).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Incluye anuncio de información pública de proyecto (jul 2026).
- **IDECyL WFS:** 18 features (1 instrumento NUM, 3 planes parciales, 14 sectores) con geometría en EPSG:4326.
- **Sin visor de expedientes** municipal ni API JSON de listado histórico completo en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Tablón actual muestra principalmente empleo público, subvenciones y anuncios generales; ocasionalmente información pública urbanística.
- Formularios/modelos en web: solicitud obras mayores, declaración responsable obras menores, prórroga licencia.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia o urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1), `urbanismo:plau_cyl_planes_parciales` (3), `urbanismo:plau_cyl_sectores` (14)
  - Filtro: `n_mun = 'Cubillos del Sil'` (c_mun `24064`, provincia León)
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_titulo`, `url_doc_info`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP/tablón por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Planos PDF de clasificación del suelo sin coords embebidas.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo muestra anuncios recientes (sin archivo scrapeable).
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio berciano (~1.500 hab.); volumen bajo de publicaciones urbanísticas activas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 5 entradas en CSV).
