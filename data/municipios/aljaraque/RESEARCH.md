# Aljaraque — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `aljaraque` |
| INE | 21005 |
| Provincia | Huelva |
| CCAA | Andalucía |
| Boletín | BOJA (`boja`) |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.aljaraque.es |
| Urbanismo | https://www.aljaraque.es/es/areas-tematicas/urbanismo/ |
| Planeamiento | https://www.aljaraque.es/es/areas-tematicas/urbanismo/el-planeamiento/ |
| Planes parciales (PDFs) | https://www.aljaraque.es/es/areas-tematicas/urbanismo/el-planeamiento/planes-parciales/ |
| Modificaciones PGOU | https://www.aljaraque.es/es/areas-tematicas/urbanismo/el-planeamiento/modificaciones-puntuales-pgou/ |
| Estudios de detalle | https://www.aljaraque.es/es/areas-tematicas/urbanismo/el-planeamiento/estudio-de-detalle/ |
| Adaptación LOUA | https://www.aljaraque.es/es/areas-tematicas/urbanismo/el-planeamiento/adaptacion-a-la-loua/ |
| Transparencia PGOU | https://www.aljaraque.es/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00002/ |
| Sede electrónica | https://aljaraque.sedelectronica.es/info.0 |
| Tablón Dip. Huelva | https://sede.diphuelva.es/opencms/system/modules/gsede/elements/contenido/TablonAnuncios.jsp |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |

## CMS y formato de datos

- **Web corporativa:** OpenCms / **SAGA Suite** con skin `com.saga.sagasuite.theme.diputacion.huelva.base` (plataforma Diputación de Huelva).
- **Expedientes / planeamiento:** documentos estáticos en galerías bajo `/export/sites/aljaraque/es/.galleries/areas-tematicas/Urbanismo/pdf/` y transparencia (`Transparencia-en-Materia-de-Urbanismo/PGOU/`). Listado HTML con enlaces directos a PDF.
- **Licencias:** no hay dataset ni tablón municipal público accesible. La sede `aljaraque.sedelectronica.es` no responde en el entorno del agente (timeout). Guías informativas en urbanismo («Cómo hacer una obra en casa», FAQ licencias).
- **Tablón provincial:** sede Diputación Huelva (GSede/EPICSA) requiere interacción/autenticación; no expone API ni listado filtrable por INE 21005 sin sesión.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** web urbanismo (sin visor SIG), transparencia (solo PDFs/planos raster), sede municipal (inaccesible), SITUA Junta (consulta genérica sin enlace por expediente del ayuntamiento), Diputación Huelva (sin WFS de expedientes).
- **Estrategia:** el adapter publica metadatos de PDFs de planeamiento; el orquestador aplica centroide municipal + jitter (`centroid: [37.2697, -7.0231]`).
- **Limitaciones:** planos en PDF sin servicio ArcGIS/WFS público; certificado SSL inválido en `www.aljaraque.es` (se usa `insecure_ssl`); sede municipal no alcanzable para scrape de tablón.

## Licencias

Sin listado histórico público. Fuentes informativas:

- PDF «obra en casa»: `/export/sites/aljaraque/es/.galleries/areas-tematicas/Urbanismo/pdf/obras-en-casa/obra_en_casa.pdf`
- FAQ licencia de obras: `/es/areas-tematicas/urbanismo/preguntas-frecuentes/preguntas-frecuentes-licencia-de-obras/`
- Sede electrónica (trámites, sin histórico): `https://aljaraque.sedelectronica.es/info.0`

## Limitaciones generales

- Certificado SSL caducado / emisor no reconocido en `www.aljaraque.es`.
- Sede propia no responde (posible protección o indisponibilidad desde datacenter).
- Sin geometría vectorial enlazable a expedientes individuales.
