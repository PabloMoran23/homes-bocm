# Castillo de Locubín — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `castillo-de-locubin` |
| Provincia | Jaén |
| CCAA | Andalucía |
| INE | 23023 |
| Boletín | BOJA (`boletin_source_id: boja`) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://aytocastillodelocubin.org | WordPress 6.4 (tema BusinessX) |
| Formularios trámites | https://aytocastillodelocubin.org/formularios/ | PDFs autorellenables (licencias, certificado urbanístico, DR) |
| Portal transparencia | https://aytocastillodelocubin.org/portal-de-transparencia/ | Índice a anuncios, normativa, exposición pública |
| Anuncios / tablón | https://aytocastillodelocubin.org/?page_id=8460 | Secciones `collapseomatic` con PDFs (decretos, BOP, proyectos) |
| Normativa urbanística | https://aytocastillodelocubin.org/?page_id=528 | PGOU/NN.SS: memoria, anexo normas, ~20 planos PDF |
| Exposición pública | https://aytocastillodelocubin.org/?page_id=11942 | Tramitaciones en IP: delimitación suelo industrial, EDAR, ordenanzas |
| BOP provincial | https://bop.dipujaen.es/bopdigital/ | Boletín Diputación Jaén (xajax; no scrapeado) |
| Sede electrónica | http://pst.castillodelocubin.es | Portal PST Diputación Jaén — **no responde** (timeout) |
| Diputación (CMS) | https://admin.dipujaen.es/municipios/Castillo-de-Locubin/ | Portal corporativo desactivado (404) |

## Cómo se listan expedientes / proyectos

1. **Exposición pública** (`page_id=11942`): secciones colapsables con título del expediente y enlaces a memoria/BOP. Incluye delimitación área reserva suelo industrial (Castillo y Ventas del Carrizal), EDAR, ordenanza solares ruin osos, evaluación ambiental, etc.
2. **Normativa urbanística** (`page_id=528`): listado estático de PDFs del planeamiento vigente (adaptación parcial LOUA de NN.SS., aprobado 2010; revisión publicada BOJA 2024).
3. **Anuncios** (`page_id=8460`): tablón general con decretos y publicaciones BOP; filtrado por keywords urbanísticas (proyecto EDAR 2023, estudio acústico AAU, etc.).
4. **WP REST API**: `GET /wp-json/wp/v2/pages/{id}` devuelve HTML embebido en `content.rendered` — usado por el adapter.

## Cómo se publican licencias

- **No hay listado público de concesiones** de licencias de obra con dirección/coords.
- **Formularios** (`/formularios/`): plantillas PDF para solicitud licencia obra mayor/menor, certificado urbanístico, declaración responsable actuaciones urbanísticas — envío por email a info@aytocastillodelocubin.org.
- **Sede electrónica** (pst.castillodelocubin.es): inaccesible; no hay tablón espublico/gestiona.
- El adapter devuelve trámites informativos (formularios) + filas del tablón que mencionen licencias.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - Normativa urbanística: cartografía solo en PDF (planos clasificación suelo, sistemas generales) sin GeoJSON/WFS.
  - `ide.dipujaen.es` WFS GetCapabilities → 404 (servicio no operativo).
  - SITUA difusión (Junta): planeamiento digitalizado escaneado, sin geometría vectorial consultable por expediente.
  - No hay visor ArcGIS/GeoJSON municipal ni enlace ref. catastral en tablón.
- **Estrategia:** sin fuente GIS; el orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** sede PST caída; geometría solo en planos PDF no machine-readable; municipio pequeño (~4.700 hab.).

## Limitaciones

- Sede electrónica `pst.castillodelocubin.es` no responde (timeout).
- Tablón de anuncios mezcla urbanismo con subvenciones, fiestas y empleo — requiere filtrado por keywords.
- Sin dataset abierto de licencias concedidas.
- BOP Diputación Jaén usa xajax/ISO-8859-1; no integrado en adapter.
