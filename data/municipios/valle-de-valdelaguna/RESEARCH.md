# Valle de Valdelaguna — investigación portal ayuntamiento

Municipio de la provincia de Burgos (CYL). INE código **09414**, PLAU municipio **414**, provincia **09**.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.valledevaldelaguna.es/ | Drupal 10 + tema Toools (Diputación Burgos) |
| Información general | https://www.valledevaldelaguna.es/informacion-general | Enlace a PLAU JCyL |
| Noticias | https://www.valledevaldelaguna.es/noticias | Anuncios urbanísticos (modificación NUM, etc.) |
| Sede electrónica | https://valledevaldelaguna.sedelectronica.es/ | espublico gestiona (Wicket) |
| Tablón de anuncios | https://valledevaldelaguna.sedelectronica.es/board | Tabla HTML con preview-document (vacío a sep/2026) |
| Transparencia | https://valledevaldelaguna.sedelectronica.es/transparency | Portal transparencia sede |
| PLAU aprobado | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=414 | NUM y modificaciones |
| PLAI info pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=414 | Sin documentos activos |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | Capas PLAU CyL |

## Proyectos / expedientes

1. **PLAU JCyL** — tabla HTML con instrumentos aprobados (NUM 2014, modificación 2023 expediente 193/21W).
2. **IDECyL WFS** — `urbanismo:plau_cyl_instrumentos_ambito` con delimitación municipal (1 feature).
3. **Drupal noticias** — anuncios de información pública (p. ej. modificación puntual normas subsidiarias).
4. **Tablón sede** — estructura espublico estándar (`/board`, preview-document); sin filas urbanísticas al scrapear.

## Licencias

- Tablón de anuncios **sin licencias publicadas** (sep/2026).
- Catálogo de trámites en sede (`/catalog`) renderizado por JS; no expone UUIDs en HTML estático.
- Adapter devuelve **páginas informativas** (tablón, catálogo, información general, sede).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun = 'Valle de Valdelaguna'` → 1 MultiPolygon (límite municipal / NUM).
  - Sin sectores ni planes parciales en WFS (`plau_cyl_planes_parciales`, `plau_cyl_sectores` → 0 features).
  - Sin visor ArcGIS municipal propio.
- **Estrategia:** query WFS por municipio; para documentos PLAU con subtipo NUM, adjuntar polígono del instrumento de ámbito; sector lookup por código si aparece en título.
- **Limitaciones:** municipio pequeño sin sectores/PP desglosados en IDECyL; tablón sin coords; licencias no georreferenciadas.

## Limitaciones generales

- DNS `valledelaguna.es` no resuelve; dominio correcto es `valledevaldelaguna.es`.
- Sede dossier (`/dossier`) responde muy lento (>40s); no usado como fuente principal.
- Certificado SSL sede puede requerir `insecure_ssl: true`.
