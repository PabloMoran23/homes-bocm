# Oleiros — investigación portal ayuntamiento

**Municipio:** Oleiros (`oleiros`)  
**Provincia:** A Coruña  
**Comunidad:** Galicia  
**INE concello:** 15058  

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web corporativa | https://www.oleiros.org |
| Urbanismo (índice) | https://www.oleiros.org/es/urbanismo |
| Ordenacións en tramitación | https://www.oleiros.org/es/concejalia-de-interior-y-seguridad-ciudadana-econom%C3%ADa-y-hacienda-urbanismo/urbanismo/ordenaciones-urbanisticas-en-tramitacion |
| Ordenacións aprobadas | https://www.oleiros.org/es/concejalia-de-interior-y-seguridad-ciudadana-econom%C3%ADa-y-hacienda-urbanismo/urbanismo/ordenaciones-urbanisticas-aprobadas |
| PXOM / plan xeral | https://www.oleiros.org/es/concejalia-de-interior-y-seguridad-ciudadana-econom%C3%ADa-y-hacienda-urbanismo/urbanismo/plan-general |
| GIS plan xeral | https://www.oleiros.org/es/concelleria-de-interior-y-seguridad-ciudadana-econom%C3%ADa-y-hacienda-urbanismo/urbanismo/gis-plan-general |
| Sede STA — tablón | https://sede.oleiros.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES |
| Sede STA — catálogo | https://sede.oleiros.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15058&lang=es_ES |

## CMS y formato

- **Web:** Liferay (tema `aytooleiros`), contenidos estáticos y documentos en `/documents/39407/...`.
- **Sede:** STA/TAO (mismo patrón que Santiago de Compostela): datasets JavaScript embebidos `dataset_PTS2_TABLON`, `dataset_CATSERV`.
- **Planeamiento regional:** SIOTUGA — POST `query_document.php` con token de sesión (cookie jar) e `idclase` 13 (desenvolvemento) / 14 (xeral).

## Expedientes / proyectos

- Listado principal en Liferay: planes parciales, PERIs, estudios de detalle, modificacións puntuales (HTML + PDFs).
- Inventario normativo Xunta: ~20 documentos clase xeral (PXOM) + instrumentos de desenvolvemento en SIOTUGA.
- Tablón municipal: anuncios varios; pocos con texto urbanístico explícito (alleamentos de parcelas, compensacións).

## Licencias

- **No hay dataset público** de licencias concedidas con dirección/fecha.
- Catálogo sede: **33 trámites** con keyword `37.URBANISMO` (licenzas, declaracións responsables, informes urbanísticos).
- El adapter expone esas páginas informativas + cualquier anuncio de tablón que mencione licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** La página «GIS plan xeral» enlaza al visor Xunta `http://mapas.xunta.gal/visores/aproveitamentos/` (planeamento autonómico / aproveitamentos), **sin** capa municipal consultable por código de expediente ni WFS del concello.
- **Estrategia:** No hay join expediente→polígono; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** Visor municipal no expone ArcGIS/MapServer propio; documentación solo PDF/planos estáticos en Liferay.

## Limitaciones generales

- User-Agent requerido en web (403 sin UA en algunos endpoints).
- SIOTUGA exige misma sesión HTTP (cookies) para token válido.
- Tablón STA no filtra por área de urbanismo; filtrado por regex en título.
