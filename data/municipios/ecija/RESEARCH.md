# Écija — investigación portal ayuntamiento

**Municipio:** Écija (Sevilla, Andalucía)  
**Slug:** `ecija`  
**Boletín:** sin boletín asociado en cola (`bocm_count: 0`)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.ecija.es | **Operativa** — WordPress + LiteSpeed |
| Área urbanismo | https://www.ecija.es/ayuntamiento/gobierno-municipal/area-de-urbanismo-obras-publicas-y-movilidad/ | Descripción competencias (PEPRICCHA, licencias, movilidad) |
| Impresos oficiales | https://www.ecija.es/ayuntamiento/impresos-oficiales-de-solicitud/ | PDFs modelos I-00, I-01, I-15, I-16 (urbanismo) |
| Registro entidades urbanísticas | https://www.ecija.es/registro-de-entidades-urbanisticas-colaboradoras-de-la-administracion-del-ayuntamiento-de-ecija/ | PDF registro |
| Sede electrónica | https://ecija.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://ecija.sedelectronica.es/board | Tabla HTML `class_name` / `preview-document/{uuid}` |
| Transparencia (indicadores) | https://ecija.sedelectronica.es/transparency | Sección «7. URBANISMO…» (~226 documentos) |
| Catálogo trámites | https://ecija.sedelectronica.es/dossier | Trámites sin histórico público de concesiones |
| Servicio ciudadano urbanismo | https://ecija.sedelectronica.es/citizen-service/7c0d772b-8124-44d7-a151-2166d0a0f60b | Enlace menú sede |
| IDE municipal | http://94.130.11.214:5000/ide/index | Kosmo — capas WMS configurables |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento digitalizado (INE **41038**) |

## Cómo se listan expedientes / proyectos

1. **Noticias municipales (WP REST):** `wp-json/wp/v2/posts` — actuaciones recientes (ATU-NU-02 «Camino del Físico», ATU San Pablo, UPR-4, PEPRICCHA, convenios urbanización).
2. **Sitemap de entradas:** `post-sitemap.xml` — URLs permanentes de noticias urbanísticas.
3. **Tablón sede:** filas con expediente, procedimiento y enlace `preview-document`; en la muestra vigente predominan convocatorias de pleno/RRHH (filtrado en adapter).
4. **Transparencia sede:** documentos bajo indicador urbanismo (Wicket/AJAX); no hay API JSON pública sin sesión.
5. **SITUA:** consulta regional de instrumentos de planeamiento (PDF), no listado de expedientes de licencia del ayuntamiento.

## Licencias de obra

- No hay registro histórico scrapeable de licencias concedidas con dirección/coordenadas.
- **Tablón:** canal legal para edictos de licencias/actividad cuando se publiquen.
- **Impresos web:** modelos de solicitud, comunicación previa y consulta viabilidad (`/wp-content/uploads/impresosoficiales/urbanismo/`).
- **Sede /dossier:** trámites electrónicos (requieren identificación para instancias).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - IDE Kosmo (`http://94.130.11.214:5000/ide/index`) expone WMS vía `client/wms/getClientCategories/1` — mapas de referencia, sin campo de enlace a código de expediente del tablón.
  - SITUA: documentos PDF de planeamiento, sin servicio FeatureServer por expediente municipal.
  - Noticias y transparencia: PDFs e imágenes sin GeoJSON/WFS enlazable por fila de proyecto.
- **Estrategia:** sin query GIS determinista por expediente; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** visor IDE en IP directa (no HTTPS); tablón paginado (~10 filas visibles); transparencia con navegación AJAX.

## Adapter implementado

- `municipio.adapters.ecija:EcijaAyuntamientoAdapter`
- Fuentes: tablón sede + noticias WP + sitemap posts + PDFs impresos urbanismo + fila SITUA + páginas informativas licencias.
- IDs: `ecija-lic-*` / `ecija-proy-*` (sha256[:14]).
