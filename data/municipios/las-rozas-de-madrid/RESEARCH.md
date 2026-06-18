# Las Rozas de Madrid — investigación portal ayuntamiento

**Fecha:** 2026-06-18  
**Slug:** `las-rozas-de-madrid`  
**BOCM regional (referencia):** 61 filas

## Resumen

Las Rozas publica planeamiento y trámites urbanísticos en **dos portales complementarios**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.lasrozas.es | Drupal 10 | Urbanismo, PGOU/NPGOU, Portal del Ciudadano (trámites licencia) |
| Transparencia | https://transparencia.lasrozas.es | WordPress | Ordenación del territorio, planes parciales, modificaciones PGOU, convenios, actas comisiones de obras |
| Sede electrónica | https://sede.lasrozas.es | (propietario) | Catálogo de trámites; **home con bucle de redirección 302** |

## Fuentes de proyectos / expedientes

### 1. Portal Transparencia (WordPress)

- **Ordenación del territorio:** https://transparencia.lasrozas.es/ordenacion-del-territorio-y-obras/
- **Planes parciales:** https://transparencia.lasrozas.es/ordenacion-del-territorio-y-obras/planes-parciales/
- **Mapas y planos PGOU:** https://transparencia.lasrozas.es/ordenacion-del-territorio-y-obras/mapas-y-planos-pgou/
- **Modificaciones PGOU:** https://transparencia.lasrozas.es/obras-publicas-y-urbanismo/modificaciones/
- **Normas PGOU:** https://transparencia.lasrozas.es/obras-publicas-y-urbanismo/normas-pgou/
- **Actas comisiones de obras:** https://transparencia.lasrozas.es/actas/comisiones-de-obras/

Formato: HTML estático con enlaces a PDF en `wp-content/uploads/`. Sin API JSON pública de expedientes; el REST API de WP (`/wp-json/wp/v2/pages`) solo indexa páginas de alto nivel.

### 2. Web Drupal — PGOU / NPGOU

- **PGOU:** https://www.lasrozas.es/urbanismo-conservacion-y-medio-ambiente/urbanismo/PGOU
- PDFs en `/sites/NPGOU/DOCUMENTO URBANISTICO PRELIMINAR/` (decenas de planos y memorias del nuevo PGOU).

### 3. Convenios (transparencia)

- Listado: https://transparencia.lasrozas.es/contratos-convenios-concesiones-y-subvenciones/convenios/
- Incluye convenios urbanísticos (p. ej. consorcio urbanístico Ciudad Universitaria). Se filtran por palabras clave urbanísticas.

## Fuentes de licencias

**No hay tablón de anuncios público** con concesiones de licencia indexable (a diferencia de Móstoles/Getafe).

Fuentes disponibles:

1. **Portal del Ciudadano — Urbanismo:** https://www.lasrozas.es/gestiones-y-tramites/PortaldelCiudadano/Urbanismo  
   Catálogo de trámites (licencia obra mayor, piscina, parcelación, comunicación inicio obras, etc.). Son páginas informativas de procedimiento, no concesiones publicadas.

2. **Sede electrónica — trámites individuales:** URLs tipo `https://sede.lasrozas.es/catalog/t/{uuid}` responden 200 con SSL no verificado, pero la portada `info.0` entra en bucle de redirección.

3. **Actas comisiones de obras:** pueden mencionar licencias en PDF; no se parsean en esta v1 (solo metadatos de acta).

## Limitaciones

- Sede electrónica inaccesible por bucle 302 en la home; solo URLs de catálogo directas.
- Sin listado machine-readable de licencias concedidas (sin geolocalización).
- Transparencia WP: muchos PDFs genéricos (alegaciones, capítulos PGOU); se filtran por regex de planeamiento.
- No replicar pipeline Madrid capital (`sector_geometry/madrid_*`).

## Estrategia de ingesta

Adapter híbrido estilo Pozuelo (Drupal PDF crawl) + transparencia WordPress:

- **proyectos.jsonl:** PDFs y enlaces de páginas semilla transparencia + PGOU Drupal + convenios urbanísticos.
- **licencias.jsonl:** paneles del Portal del Ciudadano con trámites de licencia (paridad informativa, `min_rows: 0`).
