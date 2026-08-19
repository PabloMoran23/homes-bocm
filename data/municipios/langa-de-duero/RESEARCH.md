# Langa de Duero — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `langa-de-duero` |
| Provincia | Soria (42) |
| CCAA | Castilla y León |
| Boletín | BOCYL (`boletin_source_id: bocyl`) |
| Población | ~695 hab. |

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web corporativa | https://www.langadeduero.es | Drupal 7 (bootstrap_subtheme) |
| Sede electrónica | https://langadeduero.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://langadeduero.sedelectronica.es/board | HTML tabla + preview-document |
| Catálogo trámites | https://langadeduero.sedelectronica.es/dossier | HTML enlaces `/catalog/t/...` |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=42&municipio=103 | HTML paginado |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | GeoJSON WFS 2.0 |

### Páginas Drupal relevantes

- `/actualidad/ya-esta-disponible-la-nueva-normativa-urbanistica-de-langa-de-duero` — NUM 2017
- `/actualidad/concentracion-parcelaria-de-langa-de-duero` — PDFs estudio técnico
- `/actualidad/concentracion-parcelaria-de-langa-de-duero-ii-regadio` — regadío
- `/ordenanzas` — ordenanzas fiscales (pocas urbanísticas)
- `/anuncios-particulares` — avisos ciudadanos

## Cómo se listan expedientes / proyectos

1. **PLAI JCYL** (principal): publicaciones de planeamiento (NUM, PU, GU) con `doOpen(docId)` → PDF descargable. Código municipio PLAI: `42103`.
2. **IDECyL WFS**: 8 polígonos (1 instrumento ámbito, 1 plan parcial, 6 sectores) con campos `n_sector`, `n_num_sect`, `c_id_sect`.
3. **Drupal**: noticias con PDFs embebidos en `/sites/langadeduero.es/files/public/...`.
4. **Tablón sede**: pocas entradas (electores, IAE, bando conservación); sin licencias urbanísticas publicadas actualmente.

## Cómo se publican licencias

- **Tablón**: sin licencias de obra publicadas en el momento de la investigación.
- **Trámites sede**: catálogo incluye «Solicitud de Licencia o Autorización Urbanística», «Declaración Responsable o Comunicación en Materia Urbanística», «Solicitud de Certificado o Informe Urbanístico» — páginas informativas, no concesiones.
- El adapter devuelve páginas de trámite informativas (patrón Pozuelo/Laguna de Duero).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 6 sectores con polígono WGS84
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono ámbito PGOU
  - WFS `urbanismo:plau_cyl_planes_parciales` — 1 polígono plan parcial
  - Filtro: `CQL_FILTER=n_mun='Langa de Duero'`
  - Campos enlace: `c_id_sect`, `n_sector`, `url_doc_info`
- **Estrategia:** descarga WFS por capa; enriquecimiento por coincidencia de título/sector en filas PLAI y Drupal; sectores conocidos: Vega de Alcozar I/II/III, Gatopardo, Área Ferroviaria.
- **Limitaciones:**
  - No hay visor ArcGIS propio del ayuntamiento.
  - Licencias del tablón no llevan geometría (solo PDFs administrativos).
  - Web corporativa requiere `insecure_ssl: true` (certificado rechazado por algunos clientes TLS estrictos).
  - PLAI no expone geometría; solo documentos PDF.

## Limitaciones generales

- Portal Drupal 7 antiguo, poco contenido urbanístico activo.
- Tablón sede con muy pocas publicaciones.
- Sin API JSON pública; scrape HTML determinista.
- Sin licencias de obra con coordenadas publicadas.

## Referencias técnicas

- Adapter patrón: `laguna_de_duero.py` (misma provincia/CCAA, PLAI+WFS+espublico).
- Código PLAI: provincia `42`, municipio `103` (prefijo expedientes `42103`).
