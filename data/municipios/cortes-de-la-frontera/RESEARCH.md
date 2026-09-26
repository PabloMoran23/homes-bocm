# Cortes de la Frontera — investigación portal ayuntamiento

**Municipio:** Cortes de la Frontera (Málaga, Andalucía)  
**Slug:** `cortes-de-la-frontera`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 29046

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.cortesdelafrontera.es | **Operativa** — plataforma Diputación Málaga (`static.malaga.es`); requiere UA navegador (403 CloudFront sin él) |
| Portal informativo | https://www.cortesdelafrontera.com | Landing Arundanet (redirige a .es) |
| Sede Diputación Málaga | https://sede.malaga.es/cortesdelafrontera | **Timeout SSL** en CI (handshake >60s) |
| Tablón de anuncios | https://sede.malaga.es/cortesdelafrontera/tablon-de-anuncios/ | Misma sede Diputación; no accesible desde CI |
| Sede espublico (legacy) | https://cortesdelafrontera.sedelectronica.es | **Inactiva** — mensaje «Sede Electrónica temporalmente inactiva» |
| Transparencia Diputación | http://www.malaga.es/gobiernoabierto/portal/entidad/ent-770/cortesdelafrontera | **403 CloudFront** en CI |
| PGOU / planeamiento | https://www.cortesdelafrontera.es/12046/planeamiento-urbanistico-pgou | Enlaces a SITUA Junta de Andalucía |
| Formularios DR | https://www.cortesdelafrontera.es/8233/.../formularios-declaraciones-responsables | **11 PDFs** (anexos declaración responsable) |
| Licencias de obra | https://www.cortesdelafrontera.es/12044/informacion-sobre-solicitudes-de-licencia-de-obra | Trámite informativo |
| Licencias apertura | https://www.cortesdelafrontera.es/12050/informacion-para-las-peticiones-de-licencia-de-apertura | Trámite informativo |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento digitalizado por municipio |

## Web municipal (Diputación Málaga CMS)

- **CMS:** Plataforma corporativa Diputación de Málaga (`static.malaga.es/municipios/`).
- **Acceso:** requiere `User-Agent` de navegador; sin él devuelve 403 CloudFront.
- **Sección urbanismo** (menú trámites):
  - Información licencia de obra (12044)
  - Petición informe ADIF para licencias con limitación ferroviaria (12045)
  - Planeamiento urbanístico PGOU (12046) → enlaza SITUA
  - Petición informe carreteras Diputación (12047)
  - Petición informe carreteras Junta (12048)
  - Solicitud sondeo/pozo (12049)
  - Información licencia de apertura (12050)
  - Licencia animales peligrosos (12051)
- **Formularios declaraciones responsables:** 11 anexos PDF en `static.malaga.es/municipios/subidas/archivos/`:
  - ANEXO 1–2: Declaración responsable
  - ANEXO 3–11: Ocupación, cambio de uso, comunicación previa, obra menor, etc.

## Sede electrónica

- **Activa:** `sede.malaga.es/cortesdelafrontera` (gestionada por Diputación de Málaga, no espublico).
- **Inactiva:** `cortesdelafrontera.sedelectronica.es` (espublico gestiona legacy).
- **Tablón:** HTML en sede.malaga.es; no accesible desde entorno CI por timeout SSL.
- **Consulta expedientes:** requiere autenticación en sede Diputación.

## Licencias de obra

- No hay dataset público de concesiones históricas con coordenadas.
- Formularios PDF de declaraciones responsables en web municipal (11 anexos).
- Trámites informativos en sección urbanismo de la web.
- Edictos de licencias publicados en tablón sede.malaga.es (no scrapeable en CI).

## Proyectos / planeamiento

- **PGOU:** página municipal enlaza a SITUA (Junta de Andalucía) para consulta del planeamiento digitalizado.
- **SITUA:** `planeamientoGeneralCompartir.jsf` con código municipio 29046 (CORTES DE LA FRONTERA).
- **BOJA:** 1 entrada histórica en dataset regional.
- Sin visor de seguimiento de expedientes público fuera del tablón sede.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PRP Málaga / Diputación: `https://gis.prpmalaga.es/` — visores cartográficos provinciales (PGOU por municipio); sin ArcGIS REST accesible desde CI.
  - SITUA/VITUA (Junta de Andalucía): planeamiento regional digitalizado; sin enlace por expediente del tablón.
  - Web municipal: sin visor urbanístico interactivo enlazado a expedientes.
- **Estrategia:** los visores provinciales muestran zonificación PGOU, **sin campo de enlace a expediente** del tablón. Los anuncios y formularios son PDF sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - Sede sede.malaga.es con timeout SSL en CI impide extraer tablón.
  - Transparencia Diputación bloqueada por CloudFront en CI.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Dos sedes: espublico inactiva, Diputación activa pero inaccesible en CI.
- Web municipal requiere UA navegador (no bot genérico).
- Tablón sede.malaga.es con timeout SSL (>60s handshake).
- Transparencia malaga.es bloqueada (403 CloudFront).
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.cortes_de_la_frontera:CortesDeLaFronteraAyuntamientoAdapter`
- Fuentes: web municipal (tramites + formularios PDF) + SITUA PGOU + intento tablón sede.malaga.es.
- IDs: `cortes-de-la-frontera-lic-*` / `cortes-de-la-frontera-proy-*` (sha256[:14]).
