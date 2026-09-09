# Almuñécar — investigación portal ayuntamiento

**Municipio:** Almuñécar (Granada, Andalucía)  
**Slug:** `almunecar`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 18030

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web municipal | https://www.almunecar.es | **WAF/captcha** en CI (F5 BIG-IP, error 338) |
| Portal transparencia | https://portaltransparencia.almunecar.es | **Operativo** — WordPress, planeamiento e IP urbanística |
| Urbanismo e infraestructuras | https://portaltransparencia.almunecar.es/medioambiental-urbanisticay-deinfraestructuras/ | PDFs PGOU, MP, estudios, ARI |
| Información pública urbanismo | https://portaltransparencia.almunecar.es/informacion-publica-urbanismo-e-infraestructuras/ | Consultas públicas activas |
| Planeamiento PGOU'87 | https://portaltransparencia.almunecar.es/medioambiental-urbanisticay-deinfraestructuras/planeamiento/ | Normativa, planos MP.1–MP.25, modificaciones |
| Avance PGOU | https://portaltransparencia.almunecar.es/medioambiental-urbanisticay-deinfraestructuras/avance-pgou/ | Revisión PGOU |
| Sede electrónica | https://almunecar.sedelectronica.es | **Operativa** — espublico gestiona (`insecure_ssl`) |
| Tablón de anuncios | https://almunecar.sedelectronica.es/board/ | Tabla HTML ~10 filas recientes |
| Catálogo trámites | https://almunecar.sedelectronica.es/dossier | Timeout frecuente en CI |
| Consulta expedientes | https://almunecar.sedelectronica.es/expedientes | Requiere autenticación |
| SITUA PGOU | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41236 | Enlace oficial desde portal transparencia |
| BOP Diputación Granada | https://bop.dipgra.es | Anuncios PGOU (PDF, p. ej. exp. 7374/2024) |

**Nota:** `news.almunecar.info` no responde. La documentación urbanística activa está en `portaltransparencia.almunecar.es`.

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), patrón Andalucía (Alcaucín, Cómpeta, Alhama de Granada).
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** solo primera página visible en HTML estático (~10 anuncios recientes).
- **Categorías urbanísticas observadas:** «Licencias de Actividad» (edictos IP bar/restaurante C/ Marquita).

## Licencias de obra

- No hay dataset público histórico de concesiones con coordenadas.
- Trámites vía sede (`/dossier`, `/expedientes` con login).
- Edictos de licencias/actividad publicados en tablón cuando procede.
- El adapter incluye páginas informativas (tablón, catálogo sede, portal transparencia).

## Proyectos / planeamiento

- **Portal transparencia:** secciones de planeamiento e información pública con decenas de PDFs/ZIPs (PGOU'87, MP, ARI Taramay, ATU, estudios de detalle/ordenación, modificaciones puntuales Las Maravillas, El Salao, MP98 La Herradura, etc.).
- **REST WP:** `/wp-json/wp/v2/pages` accesible; el adapter scrapea HTML de páginas semilla.
- **Tablón sede:** anuncios BOP/edictos de licencias y actuaciones urbanísticas recientes.
- **SITUA:** enlace al PGOU vigente en Junta de Andalucía (sin query por expediente del tablón).
- **BOP Diputación:** publicaciones de PGOU y modificaciones puntuales (referencia cruzada).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - SITUA (`ws132.juntadeandalucia.es/situadifusion`): visor regional del PGOU; sin enlace por código de expediente del tablón municipal.
  - Portal transparencia: PDFs/ZIPs con planos raster (MP.1–MP.25, estudios); sin API GeoJSON/WFS.
  - `www.almunecar.es`: bloqueado por WAF; no se pudo verificar visor propio.
  - Sede catastro: consulta parcela, no geometría de expediente municipal.
- **Estrategia:** no hay visor ArcGIS/WFS municipal accesible por código de expediente; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** documentos son PDF/ZIP; tablón paginado AJAX; consulta expedientes requiere login.

## Limitaciones generales

- Web principal (`www.almunecar.es`) bloqueada por WAF en entornos automatizados.
- Portal transparencia es la fuente principal de planeamiento (separado de la web corporativa).
- Sede con certificado que requiere `insecure_ssl: true` en CI.
- Tablón muestra solo anuncios recientes.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.almunecar:AlmunecarAyuntamientoAdapter`
- Fuentes: portal transparencia (planeamiento/IP) + tablón sede + enlace SITUA PGOU.
