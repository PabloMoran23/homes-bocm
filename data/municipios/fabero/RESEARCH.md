# Fabero — investigación portal ayuntamiento

**Municipio:** Fabero (León, Castilla y León)  
**INE:** 24070 | **PLAU JCyL:** provincia=24, municipio=070  
**Fecha investigación:** 2026-09-15

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.aytofabero.com | PHP custom (gestión interna) |
| Urbanismo | https://www.aytofabero.com/urbanismo.php | Enlace a plan de ordenación y oficina técnica |
| Plan ordenación | https://www.aytofabero.com/plan_ordenacion.php | PDFs locales + enlaces `jcyl.es/plaupdf/24/24070/...` |
| Trámites obras | https://www.aytofabero.com/medio_ambientes.php | Licencia urbanística, vados, vía pública |
| Tablón web | https://www.aytofabero.com/tablon.php | Eventos culturales (no urbanismo) |
| Sede electrónica | https://fabero.sedelectronica.es | espublico gestiona; tablón `/board/` (requiere `insecure_ssl`) |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=24&municipio=070 | Instrumentos aprobados (NUM, ED, PAU) |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | Capas `plau_cyl_sectores`, `plau_cyl_instrumentos_ambito` |

## Expedientes / planeamiento

- **Listado:** HTML estático en `plan_ordenacion.php` — bloques `<div class="separador_descarga_gris">` con título + enlace PDF (local o JCyL).
- **Documentos locales:** `plan-ordenacion/normas-urbanisticas.pdf`.
- **Documentos JCyL:** 5 PDFs en `plaupdf/24/24070/` (NUM aprobación inicial, NS, 3 modificaciones puntuales, estudio de detalle Escombrera La Reguera).
- **PlanPublica:** tabla HTML con instrumentos aprobados (NUM 2019, ED Escombrera 2010, PAU sector 2 SU 2025).
- **Sin API JSON** ni visor municipal propio; geometría vía IDECyL WFS.

## Licencias de obra

- **No hay dataset público** de licencias concedidas ni listado en tablón (sede actual: empleo público y anuncios administrativos).
- **Trámites informativos:** `tramite_medio_ambientes6.php` (licencia urbanística), `tramite_medio_ambientes5.php` (vados), `tramite_medio_ambientes7.php` (ocupación vía pública).
- Las concesiones se tramitan en registro presencial o sede; no publicadas de forma estructurada.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` filtro `c_mun='24070'` → 17 polígonos MultiPolygon (sectores ED-*, SU-NC, etc.)
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` → 1 feature (ámbito NUM)
  - Sin visor ArcGIS municipal ni enlace expediente→geometría en web del ayto.
- **Estrategia:** query WFS por `c_mun`; enriquecer proyectos con sector en título (p. ej. "SECTOR 2") vía `_attach_geometry`.
- **Limitaciones:** licencias sin coords; PDFs sin georreferencia; sede con certificado SSL inválido (`insecure_ssl`); tablón sin urbanismo reciente.

## Limitaciones generales

- Web PHP antigua, sin paginación de expedientes urbanísticos.
- Sede con redirect loop en `/` pero `/board/` accesible con SSL relajado.
- Sin datos abiertos ni ICV municipal.
- Licencias: solo páginas de trámite (paridad mínima como Pozuelo).
