# Lebrija — investigación portal ayuntamiento

**Municipio:** Lebrija (Sevilla, Andalucía)  
**Slug:** `lebrija`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.lebrija.es | **Operativa** (WAF estricto en CI sin User-Agent Mozilla; OpenCMS INPRO) |
| Portal transparencia | https://transparencia.lebrija.es | **Operativa** — OpenCMS Comentta/SagaSuite |
| Sede electrónica | https://sede.lebrija.es | **Operativa** — GSede OpenCMS (Guadaltel); certificado SSL intermitente en CI → `insecure_ssl: true` |
| Tablón INPRO | https://sede.lebrija.es/tablon-1.0/do/entradaPublica?ine=41064 | **Operativa pero vacío** (0 anuncios; la web enlaza erróneamente INE 41053 = La Luisiana) |
| Agenda Urbana | https://agendaurbana.lebrija.es | **Operativa** — noticias participación AU (rehabilitación urbana); no expedientes |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41064 | Sin instrumentos listados en tabla |
| LicytalPub Diputación | https://sedeelectronicadipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4106400D | Portal genérico; sin listado histórico de licencias concedidas |
| espublico legacy | https://lebrija.sedelectronica.es | **Inactiva** («Sede Electrónica Indeterminada») |

## Portal transparencia — indicadores urbanismo (ITA)

CMS OpenCMS con galerías PDF bajo `/export/sites/lebrija/es/transparencia/.galleries/`.

| Indicador | URL | PDFs aprox. |
|-----------|-----|-------------|
| 50 — PGOU y planos | …/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00008/ | 15 |
| 53 — Modificaciones PGOU / PP | …/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00008/ | 40 |
| 54 — Convenios urbanísticos | …/indicador/Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion-00008/ | 12 |
| 55 — Usos y destinos del suelo | …/indicador/Usos-y-destinos-del-suelo-00008/ | 2 |

Contenido PGOU: memoria de ordenación (aprobación definitiva 28/01/2016), catálogo, planos TM/NU, resumen ejecutivo. Modificaciones incluyen calificaciones ambientales, PERI «La Huerta» (Mod. 6 PGOU), etc.

## Tablón electrónico INPRO (sede GSede)

- **CMS:** INPRO tablón-1.0 embebido en sede.lebrija.es, INE correcto `41064`.
- **Listado:** tabla `displaytag` (`celdaGrid` + columnas ocultas) cuando hay anuncios.
- **Estado actual:** sin filas publicadas (solo formulario de búsqueda).
- **Nota:** el enlace en www.lebrija.es apunta a `ine=41053` (La Luisiana); el adapter usa `41064`.

## Sede GSede — trámites urbanismo

- Área `URBANISMO` vía ticket JavaScript (`ticket({area: 'URBANISMO'})`); requiere sesión/autenticación.
- Tablón de anuncios y portal transparencia Comentta enlazados desde portada sede.
- Sin catálogo scrapeable de licencias concedidas.

## Licencias de obra

- No hay dataset público de concesiones (LicytalPub / registro licencias).
- Tablón INPRO vacío; edictos de licencia no publicados actualmente.
- Trámites informativos vía sede GSede (área Urbanismo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** planos PDF en transparencia (clasificación usos, sectores) sin servicio WFS/ArcGIS público enlazable a expedientes.
- **SITUA:** búsqueda por `cid=41064` sin geometría descargable vía API.
- **Estrategia:** orquestador aplicará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** PDFs raster/vector sin georreferencia en metadatos; visor urbanístico no expuesto; www.lebrija.es bloqueado por WAF en algunos entornos CI.

## Limitaciones

- SSL intermitente en sede.lebrija.es → `insecure_ssl: true`.
- Web www.lebrija.es requiere User-Agent tipo navegador.
- Tablón vacío: proyectos proceden casi exclusivamente de transparencia (PDFs).
- Sin cruce automático BOJA en adapter (dato ya en `projects.json`).
