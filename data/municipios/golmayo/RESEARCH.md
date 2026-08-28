# Golmayo — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `golmayo` |
| Provincia | Soria (42) |
| CCAA | Castilla y León |
| Boletín | BOCYL (`boletin_source_id: bocyl`) |
| Código PLAI | provincia `42`, municipio `095` (INE 42105) |

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web corporativa | https://www.golmayo.es | Drupal 7 (bootstrap_subtheme) |
| Sede electrónica | https://golmayo.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://golmayo.sedelectronica.es/board | HTML tabla + preview-document |
| Catálogo trámites | https://golmayo.sedelectronica.es/dossier | HTML enlaces `/catalog/t/...` |
| Transparencia (ordenanzas) | https://golmayo.sedelectronica.es/transparency/286da81e-ea9f-4163-808d-47f0130242df/ | PDFs |
| PLAI aprobado | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=42&municipio=095 | HTML paginado |
| PLAI info pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=42&municipio=095 | HTML paginado |
| Normas urbanísticas (JCYL) | https://servicios.jcyl.es/PlanPublica/lmuni_plau.do?provincia=42 | Selector municipio |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | GeoJSON WFS 2.0 |

### Páginas Drupal relevantes

- `/e-l-m-fuenteboa` — expediente modificación puntual Fuentetoba (enlace a PLAI JCYL)
- Menú ayuntamiento → «Normas Urbanísticas» → PLAI JCYL

## Cómo se listan expedientes / proyectos

1. **PLAI JCYL** (principal): ~15+ documentos aprobados (NUM, PP, PPI, PE) con `doOpen(docId)` → PDF. Incluye modificaciones puntuales NUM (Fuentetoba, Camparañón…), planes parciales (Sector 8, Las Camaretas) y reordenación sector P.
2. **IDECyL WFS**: 47 polígonos (1 instrumento ámbito, 4 planes parciales, 42 sectores A–M) con campos `n_sector`, `n_num_sect`, `c_id_sect`.
3. **Tablón sede**: anuncios de aprobación de proyectos de obra (vestuarios Las Camaretas, instalaciones deportivas P.D.26) y publicaciones de planeamiento general.
4. **Drupal**: sin sección urbanismo dedicada; noticias de actualidad mayormente culturales/deportivas.

## Cómo se publican licencias

- **Tablón**: anuncios de aprobación de proyectos de obra (no licencias concedidas con datos estructurados).
- **Trámites sede**: catálogo `/dossier` con trámites de urbanismo/licencias — páginas informativas, requieren certificado para iniciar.
- No hay dataset abierto de licencias con coordenadas.
- El adapter devuelve páginas informativas de trámite (patrón Pozuelo/Langa de Duero).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 42 sectores con polígono MultiPolygon WGS84
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono ámbito
  - WFS `urbanismo:plau_cyl_planes_parciales` — 4 polígonos
  - Filtro: `CQL_FILTER=n_mun='Golmayo'`
  - Campos enlace: `c_id_sect`, `n_sector`, `url_doc_info`
- **Estrategia:** descarga WFS por capa; enriquecimiento por coincidencia de título/sector en filas PLAI y tablón; sectores conocidos: Fuentetoba, Las Camaretas, Camparañón, Sector 8, Sector P.
- **Limitaciones:**
  - No hay visor ArcGIS propio del ayuntamiento.
  - Licencias del tablón no llevan geometría (solo PDFs administrativos).
  - Sede puede requerir `insecure_ssl: true` (certificado HTTP/HTTPS mixto).
  - PLAI no expone geometría; solo documentos PDF.

## Limitaciones generales

- Municipio extenso (muchos barrios/núcleos) con planeamiento centralizado en PLAI JCYL.
- Tablón sede con pocas entradas urbanísticas activas.
- Sin API JSON pública; scrape HTML determinista.
- Sin licencias de obra con coordenadas publicadas.

## Referencias técnicas

- Adapter patrón: `langa_de_duero.py` (misma provincia/CCAA, Drupal+PLAI+WFS+espublico).
- Código PLAI: provincia `42`, municipio `095`.
