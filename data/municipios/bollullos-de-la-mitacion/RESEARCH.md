# Bollullos de la Mitación — investigación portal ayuntamiento

**Municipio:** Bollullos de la Mitación (Sevilla, Andalucía)  
**Slug:** `bollullos-de-la-mitacion`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 41016

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://bollullosdelamitacion.org | **Operativa** — Joomla 4 + SP Page Builder |
| Delegación urbanismo | https://bollullosdelamitacion.org/index.php/delegaciones-bollullos/delegacion-de-urbanismo | **Operativa** — trámites + enlaces |
| Documentos urbanísticos (IP) | https://bollullosdelamitacion.org/tr/08-urbanismo-y-obras-publicas/urbanismo-documentos | **Operativa** — ~33 expedientes con PDFs |
| PGOU / planeamiento | https://bollullosdelamitacion.org/index.php/delegaciones-bollullos/delegacion-de-urbanismo/pgou | **Operativa** — PDFs PGOU 2015 + PIBO |
| PMUS | https://bollullosdelamitacion.org/images/delegaciones/PersonalUrbanismo/PMUS/PMVSBollullos.pdf | PDF directo |
| Normativa municipal | https://bollullosdelamitacion.org/tr/09-normativa-y-acuerdos-municipales/normativa | **Operativa** — ordenanzas/tasas urbanísticas |
| Sede electrónica | https://sede.bollullosdelamitacion.es | **Operativa** — GSede OpenCMS (Guadaltel) |
| Tablón INPRO | https://sede.bollullosdelamitacion.es/tablon-1.0/do/entradaPublica?ine=41016 | **Operativa** — tabla displaytag HTML |
| Portal transparencia | https://bollullosdelamitacion.org/index.php/bollullos-abierto/portal-transparencia-bollullos | **Operativa** |
| SITUA Junta Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | NNSS vigentes + PGOM en tramitación |

## Documentos urbanísticos (exposición pública)

- **CMS:** Joomla SP Page Builder — bloque `sppb-addon-text-block` con secciones `<strong>DD/MM/YYYY título</strong>` + listas `<ul>` de PDFs.
- **Ruta PDFs:** `/images/trasparencia/DocExpoPublica/{año}/...` y `/images/trasparencia/PGOU/...`
- **Contenido:** estudios de detalle (ARI UA-R4, El Gran Poder), innovaciones NNSS ámbito E-8/PIBO, urbanizaciones (Entrecaminos, PP R2a2), actuaciones extraordinarias, reparcelaciones.
- **Parser:** regex por sección con fecha + primer enlace PDF de cada bloque.

## Tablón electrónico INPRO (sede municipal)

- **CMS:** INPRO tablón-1.0 (Sociedad Provincial de Informática de Sevilla), INE `41016`.
- **Listado:** tabla HTML `displaytag` con columnas ocultas (referencia, asunto, URL servlet) y extracto/fecha.
- **Paginación:** parámetro `d-16544-p` (10 edictos visibles en la consulta actual).
- **Documentos:** `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...`
- **Asuntos urbanismo:** código «Urbanismo»; mayoría de edictos son bandos/RRHH/información (filtrado en adapter).

### Ejemplo urbanístico (ago 2026)

| Ref | Asunto | Extracto |
|-----|--------|----------|
| 2754 | Urbanismo | Modificación autorización ADVA previa — infraestructura eléctrica HSF GELO |

## PGOU / planeamiento

- PGOU 2015 en `/images/trasparencia/PGOU/pgou2015/` (memoria, normas, planos PO001–PO004).
- NNSS subsidiarias + innovaciones PIBO sectores SUS-14/SUS-13 (E-8).
- Nuevo PGOM en redacción (2026) — web de seguimiento anunciada, sin dataset scrapeable aún.
- PMUS (Plan Municipal de Vivienda y Suelo) en PDF.

## Licencias de obra

- No hay dataset público de concesiones (LicytalPub no expuesto).
- Licencias publicadas aparecerían en tablón INPRO; histórico actual sin licencias de obra explícitas.
- Trámites urbanismo en sede vía ticket GSede (`area: URBANISMO`); catálogo sin scrape determinista.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Planos PGOU/NNSS/PIBO en PDF raster (`/images/trasparencia/PGOU/`, DocExpoPublica) — sin GeoJSON/WFS.
  - SITUA/VITUA (Junta de Andalucía): planeamiento regional sin campo expediente del ayuntamiento enlazable.
  - Certificado georreferenciación en PDF (Gran Poder reparcelación) — no servicio GIS consultable.
- **Estrategia:** documentos PDF sin georreferencia machine-readable; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos son PDF/imagen, no ArcGIS/WFS municipal.
  - Tablón INPRO sin coordenadas.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Tablón INPRO codificación ISO-8859-1/latin-1.
- Mayoría de edictos del tablón no urbanísticos (filtrado en adapter).
- Licencias: páginas informativas + tablón (sin concesiones históricas scrapeables).
- Algunos PDFs con URLs rotas (`https://images//...`).

## Adapter implementado

- `municipio.adapters.bollullos_de_la_mitacion:BollullosDeLaMitacionAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + documentos urbanismo IP + PGOU/PMUS web + normativa filtrada + enlace SITUA.
- IDs: `bollullos-de-la-mitacion-lic-*` / `bollullos-de-la-mitacion-proy-*` (sha256[:14]).
