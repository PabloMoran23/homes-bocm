# Monachil — investigación portal ayuntamiento

Municipio: **Monachil** (Granada, Andalucía). Boletín: **BOJA** (`boletin_source_id: boja`).

## Fuentes base

| Recurso | URL | Uso |
|---------|-----|-----|
| Web municipal | https://monachil.es | Urbanismo, modelos licencias, noticias (WP REST) |
| Urbanismo | https://monachil.es/urbanismo | PDFs avance planeamiento, NNSS, enlaces GeoVistas |
| Sede electrónica | https://monachil.sedelectronica.es | espublico gestiona: tablón, trámites, transparencia |
| Tablón | https://monachil.sedelectronica.es/board/ | Edictos (pocas filas públicas) |
| Trámites | https://monachil.sedelectronica.es/dossier | Catálogo licencias / DR obras |
| Transparencia | https://monachil.sedelectronica.es/transparency | Sección 5 urbanística (árbol AJAX; IP en 5.1.5 según BOP) |
| Servicio ciudadano | https://monachil.sedelectronica.es/citizen-service/90554653-e6ed-477b-b2bc-ba35bd547729 | Obras y urbanismo |
| GeoVistas RNNSS | https://app.geovistas.es/maps/widget/1695 | Normas subsidiarias 2000 |
| GeoVistas inventario | https://app.geovistas.es/maps/widget/1692 | Bienes inmuebles municipales |
| SITUADIFUSION | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional (referencia) |

## Listado de expedientes / proyectos

- **Tablón sede:** HTML tabla Wicket (`class_name`, `class_folderCode`, …) + `/preview-document/{uuid}`. En la muestra CI solo 2 anuncios no urbanísticos.
- **Transparencia:** árbol por secciones (5. INFORMACIÓN URBANÍSTICA Y MEDIOAMBIENTAL, 163 docs); las carpetas no exponen URL `/transparency/{uuid}/` estática (404); requiere navegación JS.
- **Web urbanismo:** enlaces a PDFs (`wp-content/uploads`), Box/Dropbox (cartografía NNSS), visores GeoVistas.
- **Noticias WP:** `GET /wp-json/wp/v2/posts?search=…` — consultas públicas, ordenanzas, estudios de ordenación.

## Licencias

- No hay listado histórico público de concesiones (como en otros municipios espublico).
- Trámites: declaración responsable ejecución de obras (PDF en urbanismo + dossier sede).
- El adapter devuelve páginas informativas del tablón, dossier y modelos web.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GeoVistas WFS/WMS: `https://app.geovistas.es/maps/wmsc/1695` — capas `ms:Limite_Termino_Municipal`, `ms:Zonificacion`, `ms:Limite_Suelo_Urbano`, etc. (`outputFormat=geojson` en WFS 2.0).
  - Visores embebidos widget 1695 (RNNSS) y 1692 (inventario).
- **Estrategia:** WFS `GetFeature` del término municipal (y suelo urbano si aplica) para filas de planeamiento/visores; sin enlace expediente→parcela en tablón.
- **Limitaciones:** Transparencia sin scrape estático; tablón sin coords; expedientes con IP solo tras login/JS; polígonos por expediente no publicados.

## Limitaciones generales

- SSL sede: certificado gestionado (adapter usa `insecure_ssl` si hiciera falta).
- Box/Dropbox: solo metadatos de enlace, sin descarga masiva en CI.
- Sync Supabase depende de `SUPABASE_DB_URL` en el entorno del agente.
