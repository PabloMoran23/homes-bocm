# El Barraco — investigación portal ayuntamiento

**Municipio:** El Barraco (Castilla y León, Ávila)  
**Fecha:** 2026-08-27

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (nueva) | https://www.elbarraco.org | Portal WordPress; **captcha SiteGround** bloquea scraping automatizado |
| Web legacy (activa) | https://mail.elbarraco.org | Sitio HTML estático accesible sin captcha |
| Normativa urbanística | https://mail.elbarraco.org/atencion/normativa.html | 9 PDFs NNSS (memoria, planos, modificaciones I–V, estudio detalle SUNC 1-P6) |
| Tablón municipal (legacy) | https://mail.elbarraco.org/atencion/tablon.html | PDF expediente ELEX-16-AV-0014 |
| Gestiones y trámites | https://mail.elbarraco.org/atencion/gestiones.html | Formularios PDF urbanismo (obras menores/mayor, ocupación, calificación) |
| Sede electrónica (espublico gestiona) | https://elbarraco.sedelectronica.es/board | Tablón de anuncios (~10 filas): EDTU delimitación N-403, subvenciones |
| Sede — catálogo trámites | https://elbarraco.sedelectronica.es/dossier.0 | Catálogo Wicket (lento en CI; timeout posible) |
| PlanPublica JCyl | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=022 | Índice documentación planeamiento (c_mun 05022) |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | Capas PLAU CyL filtradas por `n_mun = 'El Barraco'` |

## Cómo se listan expedientes

- **Web legacy:** páginas HTML con enlaces directos a PDF en `/pdf/normativa/` y `/atencion/pdf/`. Sin API ni paginación.
- **Tablón sede:** HTML espublico con `preview-document` (enlaces sueltos, sin tabla completa de 6 columnas). Expedientes urbanísticos recientes (p. ej. `LLE-26-AV-2020` delimitación tramo N-403).
- **PlanPublica JCyl:** índice documental del instrumento de planeamiento (NNSS 1984 + revisiones).
- **IDECyL WFS:** 6 features georreferenciadas (1 instrumento ámbito + 1 plan parcial + 4 sectores/polígonos).
- Sin visor de expedientes urbanísticos ni API JSON histórica en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en tablón.
- Formularios informativos en gestiones.html: obras menores, nueva planta, primera ocupación, alineación, agrupación, calificación urbanística.
- Tablón sede actual sin concesiones individuales de licencia (subvenciones, bandos, EDTU).
- Estrategia adapter: páginas informativas de trámites + formularios PDF + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `n_mun = 'El Barraco'` (c_mun 05022)
  - Sectores con polígono: P-11, P-12, P-13, P-15; instrumento: NNSS municipal
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer PDFs/tablón por coincidencia de código sector (SUNC, P-XX) en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - PDFs NNSS/EDTU sin coords embebidas.
  - Web nueva (elbarraco.org) bloqueada por captcha; se usa mail.elbarraco.org.
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales ni EDTU carretera N-403.

## Limitaciones generales

- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio pequeño (~2.000 hab.); volumen bajo de publicaciones urbanísticas activas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 2 entradas en CSV).
- `/dossier.0` puede tardar >25 s; el adapter continúa sin catálogo si timeout.
