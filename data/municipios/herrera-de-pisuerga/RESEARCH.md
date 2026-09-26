# Herrera de Pisuerga — investigación portal ayuntamiento

**Slug:** `herrera-de-pisuerga`  
**Provincia:** Palencia (Castilla y León)  
**INE:** 34083  
**Boletín:** BOCYL (`boletin_source_id: bocyl`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://herreradepisuerga.es | WordPress (Ayuntamiento) |
| Urbanismo (galería) | https://herreradepisuerga.es/ayuntamiento/urbanismo/ | NextGEN Gallery con documentos de planeamiento (p. ej. «Modificación de las Normas Urbanísticas») |
| Sede electrónica | https://herreradepisuerga.sedelectronica.es | espublico gestiona |
| Tablón de anuncios | https://herreradepisuerga.sedelectronica.es/board/ | PDFs preview-document (urbanismo: memoria, normativa, planos PGOU 2010) |
| Catálogo trámites | https://herreradepisuerga.sedelectronica.es/dossier/.0 | Licencias y trámites urbanísticos (requiere sesión tras tablón) |
| PLAU Junta CYL | https://servicios.jcyl.es/PlanPublica/lplanes.plau?municipio=3408380001701 | Índice planeamiento aprobado |
| PLAI (info pública) | searchVPubDocMuniPlai.do?provincia=34&municipio=83 | Sin filas al scrape (2026-09) |
| PLAU (archivo) | searchVPubDocMuniPlau.do?provincia=34&municipio=83 | Sin filas al scrape (2026-09) |

## Expedientes / planeamiento

- **Tablón sede:** documentos categoría «Urbanismo» (MEMORIA_JUSTIFICATIVA, NORMATIVA, PLANOS, etc.) publicados como `preview-document` PDF.
- **Galería WP:** títulos descriptivos en páginas `?g=10&st=N` (modificaciones normativas).
- **IDECyL WFS:** 1 instrumento (NUM — Normas Urbanísticas Municipales, BOCYL 2010-03-21) + 4 sectores con polígono.
- **PLAU web:** enlace desde urbanismo; tabla PLAU/PLAI vacía en scrape directo (instrumento accesible vía WFS `url_doc_info`).

## Licencias de obra

- No hay listado público de concesiones en tablón (solo tráfico, limpieza solares, etc.).
- **Catálogo sede:** páginas informativas de trámites (Solicitud de Licencia o Autorización Urbanística, Declaración responsable de actos y obras, etc.) — patrón Pozuelo/Valverdón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun='Herrera de Pisuerga'` (INE 34083 / `c_mun=34083`)
  - Sectores WFS: SUE-1-01 (Polígono Industrial I), SUE-1-02 (Polígono Industrial II), SUE-R-01 (Av. Santander), SUNC-1 (Carretera de Sotobañado)
- **Estrategia:** query WFS con `srsName=EPSG:4326`; enriquecer filas tablón/galería por código sector o fuzzy match título ↔ sector WFS.
- **Limitaciones:** licencias sin GIS; tablón PGOU son PDFs sin georef explícita; PLAU tabla vacía en HTML (geometría solo vía WFS).

## Limitaciones generales

- Sede espublico: catálogo dossier lento (~60s); warm-up tablón recomendado antes de dossier.
- SSL sede: certificado gestionado por nginx (sin problemas en prueba con `insecure_ssl: true`).
- Sin visor ArcGIS municipal propio; geometría regional IDECyL parcial (sectores, no parcelas de licencia).
