# Guadarrama — investigación portal ayuntamiento

**Municipio:** Guadarrama (Comunidad de Madrid)  
**Fecha:** 2026-07-14  
**BOCM regional (referencia):** 18 avisos

## Resumen

Guadarrama publica urbanismo en la web corporativa (`guadarrama.es`, CMS estático PHP/Bootstrap) y en la **sede electrónica eHome / espublico gestiona** (Wicket):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Urbanismo (normativa) | `https://www.guadarrama.es/contents/index3.php?id=30` | HTML + PDFs | Proyectos (NNSS, planes, BOCM) |
| Anuncios urbanismo | `https://www.guadarrama.es/contents/index3.php?id=42` | HTML + PDFs | Proyectos (PERI Las Cabezuelas, estudios) |
| Trámites | `https://www.guadarrama.es/contents/index3.php?id=70` | HTML acordeón | Licencias (modelos urbanismo) |
| Tablón sede | `https://ayuntamientodeguadarrama.sedelectronica.es/board` | HTML tabla eHome | Proyectos y licencias (anuncios vigentes) |
| Sede trámites | `https://ayuntamientodeguadarrama.sedelectronica.es/dossier` | eHome catálogo | Informativo licencias |
| Consulta expedientes | `https://ayuntamientodeguadarrama.sedelectronica.es/expedientes` | eHome | Requiere Cl@ve/certificado |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (id=30)

- **URL:** `https://www.guadarrama.es/contents/index3.php?id=30`
- **Contenido:** Normas Subsidiarias (texto refundido 2011, planos JPG/PDF), U.U. nº22 «Los Fresnos de la Jarosa» (certificado pleno 2024, BOCM jun 2024), Sector IX «Industrial La Mata», acceso C. Santa Emilia M-510.
- **Mecanismo:** enlaces directos a `/docs/urbanismo/*.pdf`.

### 2. Web corporativa — Anuncios urbanismo (id=42)

- **URL:** `https://www.guadarrama.es/contents/index3.php?id=42`
- **Contenido:** Plan Especial PERI Las Cabezuelas (aprobación inicial BOCM 03/06/2026), memoria, planos, estudios acústico/ambiental, inventario arbolado UA5.
- **Mecanismo:** PDFs en `/docs/urbanismo/` (actualmente embebidos en bloque HTML comentado; el adapter extrae enlaces `.pdf` igualmente).

### 3. Web corporativa — Trámites (id=70)

- **URL:** `https://www.guadarrama.es/contents/index3.php?id=70`
- **Secciones urbanismo:** «Trámites Actividades (Urbanismo)» y «Licencias Urbanísticas».
- **Documentos:** modelos licencia obra/actividad, declaración responsable, documentación piscina/demolición/parcelación, etc. en `/docs/tramites/Urbanismo/`.
- **Licencias:** fichas informativas y formularios; concesiones publicadas en tablón cuando proceda.

### 4. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://ayuntamientodeguadarrama.sedelectronica.es/board`
- **Formato:** Tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`data-label`).
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Ejemplos (jul 2026):** ordenanzas, convocatorias JGL; históricamente categoría «Urbanismo» (licencias actividad, estudios de detalle, IP).
- **Limitación:** Solo anuncios vigentes (~pocas filas); paginación vía Wicket AJAX («Mostrar más»).

### 5. Sede electrónica — Trámites y expedientes

- **Catálogo:** `/dossier` — licencias urbanísticas, actividades, consulta expedientes.
- **Consulta expedientes:** `/expedientes` — requiere identificación electrónica.
- **Registro antiguo:** `registroelectronico.guadarrama.es` — expedientes anteriores a 15/01/2024.

### 6. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| IDEM visor SITCM (`idem.madrid.org`) | Cartografía regional de planeamiento, sin enlace a expedientes municipales |
| Dropbox PERI Las Cabezuelas | Enlace externo no scrapeable de forma estable |
| BOCM re-parse | Ya cubierto en pipeline regional |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='GUADARRAMA'`.
  - Ámbitos disponibles: PERI DE LAS CABEZUELAS, S-IX INDUSTRIAL DE LA MATA, UA-C LOS FRESNOS DE LA JAROSA, PERI DE NAVALAFUENTE, sectores S-I…S-IX, etc.
  - Web urbanismo: planos PDF/JPG sin georreferencia directa.
  - Sede `/expedientes`: requiere autenticación; no expone geometría pública.
- **Estrategia:** El adapter cruza títulos PDF (palabras clave: «cabezuelas», «la mata», «fresnos», …) con ámbitos SITCM vía WFS. Sin visor municipal enlazado a expediente.
- **Limitaciones:** Normas subsidiarias, certificados genéricos y tablón sin sector identificable no obtienen polígono; el orquestador aplica centroide + jitter.

## Estrategia de ingesta

- **proyectos.jsonl:** PDFs urbanismo (id=30, id=42) + tablón sede filtrado (urbanismo, planeamiento, BOCM, IP).
- **licencias.jsonl:** Páginas informativas (urbanismo + trámites + sede) + modelos PDF `/docs/tramites/Urbanismo/` + tablón filtrado.
- **IDs:** `guadarrama-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Verificación pipeline (2026-07-21)

- Proyectos: 13 filas (`with_geometry`: ver parity-report tras enrich)
- Licencias: 20 filas (`with_geometry`: 0)
- Parity: ok (proyectos) / partial (licencias informativas)
- SITCM: polígonos parciales por palabras clave en títulos PDF

## Paridad esperada

- `proyectos`: ok (12+ documentos normativa/anuncios + tablón).
- `licencias`: partial (modelos y trámites informativos; sin listado histórico de concesiones con coordenadas).
