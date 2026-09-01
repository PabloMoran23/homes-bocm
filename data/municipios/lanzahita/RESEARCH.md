# Lanzahíta — investigación portal ayuntamiento

**Municipio:** Lanzahíta (Castilla y León, Ávila)  
**INE:** 05110  
**Fecha:** 2026-08-30

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | — | `lanzahita.es` / `www.lanzahita.es` no responden (sin portal web propio) |
| Sede electrónica (espublico gestiona) | https://lanzahita.sedelectronica.es | Portal único del ayuntamiento |
| Tablón de anuncios | https://lanzahita.sedelectronica.es/board | ~7 anuncios visibles (fiscales, administrativos) |
| Trámites | https://lanzahita.sedelectronica.es/dossier | Catálogo de trámites (responde lento o timeout) |
| Transparencia | https://lanzahita.sedelectronica.es/transparency | Sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» |
| PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=110 | Archivo planeamiento CyL (INE 05110) |

## Cómo se listan expedientes

- **Sede espublico:** tablón HTML con enlaces `preview-document` (Wicket). Sin tabla de expedientes urbanísticos activos en el tablón actual.
- **PLAU JCyL:** documentos PDF de planeamiento (NNSS 1995, revisiones) vía buscador regional.
- **IDECyL WFS:** capas PLAU CyL con geometría de instrumentos y sectores.
- Sin visor urbanístico municipal ni API JSON de expedientes.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en tablón.
- Trámites de licencia accesibles vía catálogo sede `/dossier` (cuando responde).
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Lanzahíta'`
  - Resultados: 1 instrumento (NNSS 1995) + 14 sectores/unidades de ejecución con polígono
  - Campo sector: `n_sector`, `c_id_sect` (p. ej. `05110S-1`, `05110UE-1`)
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas tablón por coincidencia de nombre de sector.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo muestra anuncios recientes (sin urbanismo activo).
  - Sin web corporativa con PDFs de planeamiento.
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.

## Limitaciones generales

- Sin dominio web municipal activo; toda la información pasa por sede electrónica.
- `/info` y `/dossier` pueden responder muy lento o timeout (>60s).
- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio pequeño (~300 hab.); volumen bajo de publicaciones urbanísticas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 2 entradas en CSV).
