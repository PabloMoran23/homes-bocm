# Arahal — investigación portal ayuntamiento

Municipio: **Arahal** (Sevilla, Andalucía)  
INE: **41005** | CIF: **P4101100H** | Boletín: **BOJA**

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (OpenCMS) | https://www.arahal.es |
| Sede electrónica (GSede/EPICSA) | https://sede.arahal.es |
| Tablón INPRO sede | https://sede.arahal.es/tablon-1.0/do/entradaPublica?ine=41005 |
| Urbanismo | https://www.arahal.es/es/temas/urbanismo/ |
| PGOU (índice documental) | https://www.arahal.es/es/ayuntamiento/pgou |
| Consulta previa ordenanzas | https://www.arahal.es/es/ayuntamiento/consulta-previa-publica-de-ordenanzas-y-reglamentos/ |
| PGOM en trámite (WP) | https://arahal.nuevoplan.es/documentos/ |
| Planes urbanísticos (Google Sites) | https://www.nuevosplanes.arahal.org/ |
| SITUA Junta Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |
| LicytalPub Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4101100H |

## Cómo se listan expedientes / planeamiento

1. **Tablón INPRO** (`sede.arahal.es/tablon-1.0`): HTML con formulario POST a `/do/anuncio/listado`. Filas en `<tr class="odd|even">` con celdas ocultas (referencia, asunto, URL). En la ejecución de investigación (2026-09) el listado devolvió **0 filas** publicadas; la infraestructura existe (asuntos incluyen «ANUNCIO LICENCIAS DE APERTURAS ESTABLECIMIENTOS», código 13).
2. **Consulta previa pública**: OpenCms — galería `.galleries/consulta-previa-publica/` con **31 PDFs** (ordenanzas, modificaciones PEPCH, exposiciones públicas).
3. **PGOM nuevo**: WordPress en `arahal.nuevoplan.es` — API REST `/wp-json/wp/v2/media` (**47** documentos PDF/imagen de fases del plan).
4. **Nuevos planes (Google Sites)**: `nuevosplanes.arahal.org` — enlaces a **4** documentos en Google Drive (memorias / cartografía planeamiento).
5. **PGOU vigente**: página `/es/ayuntamiento/pgou` con secciones acordeón (vigente, modificaciones, en tramitación); contenido cargado en cliente sin PDFs estáticos en HTML — documentación accesible vía consulta previa y nuevoplan.
6. **SITUA**: portal autonómico de difusión de planeamiento; no expone geometría por expediente municipal.

## Licencias de obra

- No hay dataset abierto de licencias con coordenadas en la web del ayuntamiento.
- **LicytalPub** (Diputación de Sevilla) centraliza consulta de licencias por CIF municipal; timeout en entorno agente — se documenta como página informativa.
- Tablón INPRO categoría 13 («licencias de aperturas establecimientos») — sin edictos activos en el momento de la investigación.
- Trámites de licencia vía sede GSede (ticket/Cl@ve); sin listado público scrapeable.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** sede INPRO (solo PDFs/edictos), OpenCms web, SITUA Junta de Andalucía (planeamiento general sin enlace expediente→polígono), Diputación Sevilla LicytalPub (licencias sin geometría), Google Drive / nuevoplan (documentación PDF).
- **Estrategia:** no hay visor ArcGIS/WFS municipal ni geoportal con campo de expediente para Arahal. El orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** planeamiento solo en PDF/Google Drive; tablón vacío; PGOU página dinámica sin API; sin datos abiertos georreferenciados.

## Limitaciones generales

- Tablón INPRO puede estar vacío temporalmente (no bloquea — otras fuentes aportan proyectos).
- `portal.dipusevilla.es` tablón también sin filas para INE 41005.
- Galerías OpenCms `/export/sites/arahal/.galleries/` devuelven 500 en listado de directorio; PDFs individuales accesibles por URL directa.
- LicytalPub con latencia alta / timeout desde CI.
