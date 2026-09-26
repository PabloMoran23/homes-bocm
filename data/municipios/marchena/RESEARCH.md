# Marchena — investigación portal ayuntamiento

**Municipio:** Marchena (Sevilla, Andalucía)  
**Slug:** `marchena`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://marchena.es | **Operativa** — WordPress |
| Sede electrónica | https://sedemarchena.dipusevilla.es | **Operativa** — GSede OpenCMS (Guadaltel / Diputación Sevilla) |
| Tablón INPRO | https://sedemarchena.dipusevilla.es/tablon-1.0/do/entradaPublica?ine=41060 | **Operativa** — tabla displaytag HTML |
| Portal transparencia | http://transparencia.marchena.es/es/ | **Operativa** — SagaSuite Diputación Sevilla |
| Indicador PGOU | http://transparencia.marchena.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00015/ | PDFs + enlace SITUA |
| Modificaciones PGOU | http://transparencia.marchena.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00015/ | ~20 PDFs actuaciones/modificaciones |
| Convenios urbanísticos | http://transparencia.marchena.es/es/transparencia/indicadores-de-transparencia/indicador/Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion-00015/ | Documentación convenios |
| Licyt@l Diputación | https://sedeelectronicadipusevilla.es/LicytalSede/jsp/index.faces?cif=P4106000E | **Operativa** — contratación local (no licencias de obra) |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/ (Marchena INE 41060) | Planeamiento aprobado — documentos PDF |

**Nota:** `marchena.sedelectronica.es` responde «Sede indeterminada»; la sede activa es `sedemarchena.dipusevilla.es`. Código INE en tablón Diputación: **41060** (escudo/CIF `P4106000E`).

## Tablón electrónico INPRO (sede Diputación)

- **CMS:** INPRO tablón-1.0 (Sociedad Provincial de Informática de Sevilla), parámetro `ine=41060`.
- **Listado:** tabla HTML `displaytag` con columnas ocultas (referencia, asunto, URL servlet) y extracto/fecha.
- **Paginación:** parámetro `d-16544-p`; ~10 edictos activos en 2 páginas (sep 2026).
- **Documentos:** `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...` y URL permanente por hash.
- **Asuntos urbanismo:** edictos bajo asunto genérico «ANUNCIO» con extracto de planeamiento/ordenanzas.

### Ejemplo urbanístico (sep 2026)

| Ref | Asunto | Extracto |
|-----|--------|----------|
| 1597 | ANUNCIO | Consulta pública previa — ordenanza municipal reguladora de la actividad económica |

## PGOU y planeamiento (transparencia + SITUA)

- Indicadores Ley Transparencia con PDFs en `.galleries/IND-50-*`, `IND-53-*`, `IND-54-*`.
- Contenido: PGOU, modificaciones de planeamiento, estudios de detalle (U.A.-50), proyectos de actuación (DESPROAVE III, energías renovables), convenios.
- SITUA Junta de Andalucía enlaza documentos de planeamiento general aprobado (codFigura 7056, INE 41060).

## Licencias de obra

- No hay registro público scrapeable de licencias concedidas (Licyt@l es contratación pública local).
- Las licencias publicadas aparecerían en tablón INPRO; en el histórico actual no hay licencias de obra explícitas.
- Trámites urbanismo en sede GSede vía registro/ticket; sin catálogo público scrapeable sin autenticación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PGOU/planos en PDF raster (transparencia `.galleries`, SITUA documentos) — sin GeoJSON/WFS.
  - SITUA/VITUA Junta: documentos de planeamiento sin servicio REST enlazable por expediente.
  - Diputación Sevilla: sin visor ArcGIS/WFS público por código de expediente del ayuntamiento.
- **Estrategia:** documentos PDF sin georreferencia; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos PGOU son PDF/imagen, no servicios ArcGIS/WFS.
  - Tablón codificación ISO-8859-1/latin-1.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Mayoría de edictos del tablón son RRHH/personal/cobranza (filtrado en adapter).
- Licencias: solo páginas informativas + tablón (sin concesiones históricas scrapeables).
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.marchena:MarchenaAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + PDFs transparencia (PGOU/modificaciones/convenios) + SITUA + páginas informativas licencias.
- IDs: `marchena-lic-*` / `marchena-proy-*` (sha256[:14]).
