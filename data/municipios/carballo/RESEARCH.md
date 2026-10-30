# Carballo — investigación portal ayuntamiento

Municipio: **Carballo** (`carballo`) — Galicia, provincia A Coruña.  
INE: **15019**. Sin boletín autonómico asociado en cola (`bocm_count: 0`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://carballo.gal/ | WordPress (Elementor): área «Urbanismo e axenda urbana». |
| Documentos en tramitación | https://carballo.gal/urbanismo-e-axenda-urbana/documentos-en-tramitacion/ | PDFs de PEID, modificaciones puntuales, expropiaciones (anuncios IP/AD). |
| Archivo PXOM | https://arquivos.carballo.gal/pxom-carballo/ | Documentación histórica PXOM (enlaces externos pxomcarballo.org). |
| Sede SXC | https://sede.carballo.gal/sxc/es/ | Plataforma Diputación A Coruña (subsede Carballo). |
| Tablón de anuncios | https://sede.carballo.gal/sxc/es/informacion/tablon/index.html | Listado HTML; búsqueda `POST query=urbanismo&search=search`. Detalle `/tablon/YYYY/ANUNCIO_PROG_*.html`. |
| Trámites urbanismo | https://sede.carballo.gal/sxc/es/procedimientosytramites/index.html#urbanismo | Licencia edificación, certificados, información urbanística (solo descriptivos + inicio telemático Cl@ve). |
| Transparencia | https://www.eidolocal.gal/gl/portal-transparencia/-/entidade/15019/visualizar | Portal eidolocal (entidad 15019). |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15019 | API `query_document.php` (clases 14 PG, 13 desarrollo) con `token` de sesión. |
| SIOTUGA estado | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | Estado normativo municipal en cartografía autonómica. |

## Expedientes / proyectos

- **Tablón sede:** sección recurrente **URBANISMO** con título en `<p class="top40">`, fecha, código `EXP: YYYY/U…` y PDFs en `/sxc/export/sites/carballo/recursos/downloads/Tablon/…`.
- **Web tramitación:** bloques Elementor con un PDF principal por actuación (PEID SXVI, MP11, Lagoa, Carpinteiros, etc.).
- **SIOTUGA:** plan xeral e instrumentos de desarrollo aprobados (metadatos, sin enlace directo a expediente del tablón).
- No hay visor de expedientes urbanísticos tipo Pozuelo (Drupal IP).

## Licencias

- **No** hay dataset ni tablón sistemático de licencias concedidas con dirección/coordenadas.
- Trámites descriptivos en sede SXC (licencia de edificación, comunicaciones, etc.) requieren identificación Cl@ve para presentación.
- Estrategia adapter: trámites informativos + anuncios del tablón que mencionen licencia/edificación (escasos).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIOTUGA / cartografía Xunta: WMS por instrumento de planeamiento (`getIotpuWMS.php?codine=15019`), no por código `EXP` del tablón.
  - Archivo PXOM y pxomcarballo.org: documentación y visor legacy, sin API REST enlazable a expedientes actuales.
- **Estrategia:** metadatos de planeamiento desde SIOTUGA + anuncios/PDF; polígonos por expediente concreto no recuperables de forma determinista desde el portal.
- **Limitaciones:** tablón solo PDF/HTML; sede SXC sin geometría en listados; SIOTUGA requiere `token` por sesión.

## Limitaciones técnicas

- Tablón: ~70 resultados por búsqueda «urbanismo»; detalle requiere una petición HTTP por anuncio.
- SIOTUGA: primera petición puede tardar; token invalidado si se reutiliza en exceso.
- Web municipal: contenido bilingüe (gl/es); URLs estables en `/wp-content/uploads/`.
