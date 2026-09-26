# Matamala de Almazán — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `matamala-de-almazan` |
| Provincia | Soria (42) |
| CCAA | Castilla y León |
| Boletín | BOCYL (`boletin_source_id: bocyl`) |
| INE | 42103 |

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web corporativa | https://www.matamaladealmazan.es | Drupal 7 (bootstrap_subtheme) |
| Sede electrónica | https://matamaladealmazan.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://matamaladealmazan.sedelectronica.es/board/ | HTML tabla + preview-document |
| Catálogo trámites | https://matamaladealmazan.sedelectronica.es/dossier | HTML enlaces `/catalog/t/...` (lento) |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=42&municipio=111 | HTML paginado |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | GeoJSON WFS 2.0 |

### Páginas Drupal relevantes

- `/normas-urbanisticas` — NUM y documentación urbanística
- `/informacion-urbanistica` — información general
- `/modificacion-puntual-no5-de-las-normas-urbanisticas-municipales` — MP NUM 5
- `/modificacion-puntual-no-6-de-las-normas-urbanisticas-municipales` — MP NUM 6 + PDFs
- `/plan-especial-de-ordenacion-de-la-finca-de-la-concepcion` — PE + estudio ambiental
- `/ordenanzas-y-reglamentos` — ordenanzas municipales
- `/bandos` — bandos municipales

## Cómo se listan expedientes / proyectos

1. **PLAI JCYL** (principal): publicaciones de planeamiento (NUM, modificaciones) con `doOpen(docId)` → PDF. Código PLAI: provincia `42`, municipio `111` (INE 42103).
2. **IDECyL WFS**: 10 polígonos (1 instrumento ámbito NUM, 9 sectores ST-Nº 1–6) con campos `n_sector`, `n_num_sect`, `c_id_sect`.
3. **Drupal**: páginas de normas urbanísticas y modificaciones con PDFs en `/sites/matamaladealmazan.es/files/public/pags/`.
4. **Tablón sede**: sin urbanismo activo (electores, jurado); sin licencias de obra publicadas.

## Cómo se publican licencias

- **Tablón**: sin licencias de obra publicadas en el momento de la investigación.
- **Trámites sede**: catálogo incluye trámites de licencia urbanística y declaración responsable — páginas informativas, no concesiones.
- El adapter devuelve páginas de trámite informativas (patrón Langa de Duero/Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 9 sectores (ST-Nº 1–6) con polígono WGS84
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono ámbito NUM
  - Filtro: `CQL_FILTER=n_mun='Matamala de Almazán'`
  - Campos enlace: `c_id_sect`, `n_sector`, `n_num_sect`, `url_doc_info`
- **Estrategia:** descarga WFS por capa; enriquecimiento por coincidencia de título/sector en filas PLAI y Drupal.
- **Limitaciones:**
  - No hay visor ArcGIS propio del ayuntamiento.
  - Licencias del tablón no llevan geometría.
  - `/dossier` de la sede responde muy lento (>45 s); el adapter tolera timeout.
  - PLAI y Drupal solo exponen PDFs sin geometría embebida.

## Limitaciones generales

- Portal Drupal 7 con contenido urbanístico concentrado en modificaciones NUM y PE Finca Concepción.
- Tablón sede sin licencias urbanísticas publicadas.
- Sin API JSON pública; scrape HTML determinista.
- Sin licencias de obra con coordenadas publicadas.

## Referencias técnicas

- Adapter patrón: `langa_de_duero.py` (misma provincia/CCAA, PLAI+WFS+espublico).
- Código PLAI: provincia `42`, municipio `111`.
