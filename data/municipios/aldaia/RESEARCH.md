# Aldaia — investigación portal ayuntamiento

**Municipio:** Aldaia (`aldaia`)  
**Provincia:** Valencia  
**CCAA:** Comunitat Valenciana  
**Boletín:** DOGV (`dogv`, 2 entradas BOCM)  
**INE:** 46005

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://aldaia.es | WordPress (Yoast SEO), sección Urbanismo i Medi ambient |
| Urbanismo (ES) | https://aldaia.es/es/urbanismo-y-medio-ambiente/ | Departamento, enlaces transparencia, PLRPIF, estudios |
| Urbanismo (VA) | https://aldaia.es/urbanisme-i-medi-ambient/ | Versión valenciana |
| Transparencia | https://transparencia.aldaia.es | Drupal 7, portal transparencia Dival/portalesmunicipales |
| Info urbanística | https://transparencia.aldaia.es/es/transparencia/informacion-urbanistica | ~280 PDFs (EATE, plan parcial, homologación, estudios, DOGV) |
| PGOU | https://transparencia.aldaia.es/es/transparencia/plan-general-ordenacion-urbana | Plan general y modificaciones |
| Modificaciones PGOU | https://transparencia.aldaia.es/es/transparencia/modificaciones-al-plan-general-ordenacion-urbana | PDFs modificativos |
| Homologaciones | https://transparencia.aldaia.es/es/transparencia/homologaciones-modificativas | Documentación homologación |
| Ordenanzas | https://transparencia.aldaia.es/es/transparencia/ordenanzas-urbanisticas | OR-URB 01–15, texto refundido PGOU |
| PLRPIF | https://transparencia.aldaia.es/es/general/transparencia/plrpif | Plan de recuperación paisajística |
| Cita previa | https://citaprevia.aldaia.eu/frontend.php | OAC / educación (sin trámites licencia explícitos) |
| Sede electrónica | https://aldaia.sedelectronica.es | **Inactiva** — página «Por favor, seleccione su sede electrónica» |

## Cómo se listan expedientes / proyectos

- **Transparencia Drupal:** listados HTML con enlaces directos a PDF en `/sites/default/files/`. Títulos en `<a title="...">` o texto del enlace. Fechas frecuentes en nombre de archivo (`YYYYMMDD_...`).
- **Web WordPress:** páginas informativas con enlaces a transparencia y PDFs en `/wp-content/uploads/`.
- **Sin visor de expedientes** ni API JSON pública de expedientes urbanísticos.
- **Sin tablón de anuncios** accesible (sede espublico no configurada para Aldaia).

## Cómo se publican licencias

- **No hay listado público** de licencias concedidas ni tablón de edictos operativo.
- Trámites presenciales / cita previa OAC; normativa en ordenanzas urbanísticas (transparencia).
- El adapter devuelve **páginas informativas** de trámites (patrón Pozuelo) con `min_rows` implícito 0 en validación de concesiones.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes investigadas:**
  - ICV WFS `https://terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion` — **sin features** con `noms_mun=Aldaia` ni `cod_ine_mun=46005` (barrido 0–16000).
  - Visor GVA (`visor.gva.es`) — sin capa enlazable a expedientes municipales de Aldaia.
  - Web: callejero PDF, sin visor ArcGIS/WFS municipal.
- **Estrategia:** no aplicable; orquestador usará centroide municipio + jitter.
- **Limitaciones:** documentación solo PDF sin georreferencia; sede inactiva; sin dataset SIG público del ayuntamiento.

## Limitaciones generales

- `www.aldaia.es` devuelve HTTP 500 sin User-Agent Mozilla; usar `aldaia.es`.
- Sede electrónica no operativa.
- Gran volumen de PDFs en información urbanística (filtrados por regex urbanismo en adapter).
- Sin geometría poligonal disponible.

## Referencias de implementación

- Patrón transparencia + WP sin sede: `torremolinos.py`
- Páginas informativas licencias: `pozuelo.py`
- ICV WFS (no aplicable aquí): `enguera.py`, `canals.py`
