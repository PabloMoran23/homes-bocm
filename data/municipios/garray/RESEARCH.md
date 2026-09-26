# Garray — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `garray` |
| Provincia | Soria (42) |
| CCAA | Castilla y León |
| Boletín | BOCYL (`boletin_source_id: bocyl`) |
| INE | 42101 |

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web corporativa | https://www.garray.es | Drupal 7 (bootstrap_subtheme) |
| Sede electrónica | https://garray.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://garray.sedelectronica.es/board | HTML + preview-document |
| Catálogo trámites | https://garray.sedelectronica.es/dossier | HTML enlaces `/catalog/t/...` |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=42&municipio=101 | HTML paginado |
| PLAU JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=42&municipio=101 | HTML (sin filas en investigación) |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | GeoJSON WFS 2.0 |

### Páginas Drupal relevantes

- `/archivos-de-planeamiento-urbanistico` — índice de normativa y expedientes
- `/modificacion-puntual-no-4-num` — modificación puntual nº 4 NUM (2026)
- `/modificacion-puntual-no-3-num-garray` — modificación puntual nº 3 NUM
- `/estudio-de-detalle-calle-olmillos-21-23-25-27-de-dombellas` — estudio de detalle Dombellas
- `/estudio-de-detalle-parcela-calle-real-30-de-canredondo-de-la-sierra` — estudio Canredondo
- `/informacion-urbanistica` — información urbanística general
- `/normas-urbanisticas-municipales-documentacion-normativa` — documentación NUM
- `/autorizacion-uso-provisional-en-suelo-urbano-no-consolidado-obras-de-escasa-entidad-constructiva-en` — usos provisionales SUNC

## Cómo se listan expedientes / proyectos

1. **IDECyL WFS** (principal geometría): 12 sectores SU-NC/SUR + 1 plan parcial «El Dinosaurio» + 1 instrumento NUM. Filtro `n_mun='Garray'`.
2. **Drupal**: páginas de planeamiento con títulos de modificaciones NUM, estudios de detalle y archivos PDF en `/sites/garray.es/files/`.
3. **PLAI JCYL**: publicaciones de información pública (si hay entradas paginadas).
4. **Tablón sede**: pocas entradas administrativas (IAE, cobranza); sin licencias urbanísticas publicadas actualmente.

## Cómo se publican licencias

- **Tablón**: sin licencias de obra publicadas en el momento de la investigación (solo anuncios fiscales/administrativos).
- **Trámites sede**: catálogo `/dossier` con trámites de urbanismo y licencias — páginas informativas, no concesiones.
- El adapter devuelve páginas de trámite informativas (patrón Langa de Duero/Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 12 sectores con polígono WGS84 (Centro, Norte 1-3, Sur 1-3, Tardestillas, Santervás, Los Negredos, Dinosaurio, El Pendón)
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono ámbito NUM
  - WFS `urbanismo:plau_cyl_planes_parciales` — 1 polígono PP «El Dinosaurio» (SUR RES 01)
  - Filtro: `CQL_FILTER=n_mun='Garray'`
  - Campos enlace: `c_id_sect`, `n_sector`, `n_num_sect`, `url_doc_info`
- **Estrategia:** descarga WFS por capa; enriquecimiento por coincidencia de título/sector en filas Drupal y PLAI.
- **Limitaciones:**
  - No hay visor ArcGIS propio del ayuntamiento.
  - Licencias del tablón no llevan geometría.
  - PLAI/Drupal no exponen polígonos; solo documentos PDF.
  - Estudios de detalle puntuales (Dombellas, Canredondo) no tienen capa WFS dedicada.

## Limitaciones generales

- Portal Drupal 7 con contenido urbanístico disperso en subpáginas.
- Tablón sede con muy pocas publicaciones urbanísticas.
- Sin API JSON pública; scrape HTML determinista.
- Sin licencias de obra con coordenadas publicadas.

## Referencias técnicas

- Adapter patrón: `langa_de_duero.py` (misma provincia/CCAA, PLAI+WFS+espublico+Drupal).
- Código PLAI: provincia `42`, municipio `101` (INE 42101, código interno 42094).
