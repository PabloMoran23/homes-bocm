# Cambre — investigación portal ayuntamiento

Municipio: **Cambre** (`cambre`), provincia A Coruña, Galicia. INE concello: **15017**.

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa | https://cambre.es |
| Urbanismo (índice) | https://cambre.es/urbanismo/?lang=es |
| Planeamento en tramitación | https://cambre.es/planeamiento-urbanistico/?lang=es |
| PXOM | https://cambre.es/plan-xeral-de-ordenacion-municipal-pxom-do-concello-de-cambre/ |
| Sede electrónica (SXC Diputación A Coruña) | https://sede.cambre.es |
| Tablón de anuncios | https://sede.cambre.es/sxc/es/informacion/tablon/index.html |
| Trámites urbanismo | https://sede.cambre.es/sxc/es/procedimientosytramites/index.html#urbanismo |
| Transparencia (OpenCMS) | https://sede.cambre.es/opencms/gl/portal_transparencia/ |
| Inventario SIOTUGA | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15017&lang=es_ES |
| Visor planeamento local | http://urbanismoenred.cambre.es:8090/Visor/ |

## Proyectos / planeamiento

1. **WordPress (Divi)** — La página de planeamento lista instrumentos aprobados (enlaces a SIOTUGA/BOP) y documentos **en tramitación** como PDFs bajo `/wp-content/uploads/urbanismotramitacion/` (SAU, PERI, modificaciones puntuales UE, etc.).
2. **SIOTUGA** — API POST `query_document.php` con token de sesión; clases 14 (plan xeral) y 13 (desenvolvemento) devuelven JSON con `docnome`, fechas y figura.
3. **Tablón SXC** — Buscador POST (`query=urbanismo`); pocas entradas recientes de urbanismo; estructura HTML `<h2>`, fecha y `<contenido>` (patrón Carballo/Arteixo).

## Licencias

No hay dataset público de licencias concedidas. La sede publica **procedimientos** (licencia de edificación, comunicación previa de primera ocupación, certificado urbanístico, etc.) en el acordeón Urbanismo del catálogo SXC.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor municipal «Urbanismo en Red» en `http://urbanismoenred.cambre.es:8090/Visor/` (enlace desde sede y tablón).
  - SIOTUGA / Xunta: inventario documental y visor autonómico; no expone polígonos por expediente vía API simple enlazable al tablón.
- **Estrategia:** El adapter documenta el visor como semilla; no hay REST ArcGIS/WFS público estable accesible desde el entorno de scraping (el visor en `:8090` no responde desde red del agente). El orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** PDFs sin georreferencia; tablón sin coords; visor posiblemente solo en red local/HTTP sin servicios MapServer expuestos al scraper.

## Limitaciones generales

- CMS bilingüe (gl/es); URLs duplicadas `planeamento` / `planeamiento`.
- Tablón con pocos anuncios urbanísticos indexables por búsqueda.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
