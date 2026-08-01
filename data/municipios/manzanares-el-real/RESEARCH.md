# Manzanares el Real — investigación portal ayuntamiento

**Municipio:** Manzanares el Real (Comunidad de Madrid)  
**Fecha:** 2026-07-21  
**BOCM regional (referencia):** 13 avisos

## Resumen

Manzanares el Real publica urbanismo en web corporativa WordPress (tema Ganesa) y sede electrónica eHome / espublico gestiona (Wicket):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://manzanareselreal.es/ordenacion-del-territorio/urbanismo/` | WordPress categoría 41 | Proyectos (noticias PGOU, obras, IP) |
| Tablón sede | `https://manzanareselreal.sedelectronica.es/board` | HTML tabla eHome | Proyectos y licencias (anuncios vigentes) |
| Transparencia normativa | `.../transparency/70fa3e9b-9aec-443a-9c20-882f0ecd03df/` | eHome dossier | Proyectos (NNSS, planes parciales, ordenanzas) |
| Servicio PGOU | `.../citizen-service/1b89ac11-06c5-41e5-bcfe-aa2b2a56b298` | eHome | Proyecto PGOU aprobación inicial |
| Sede trámites | `https://manzanareselreal.sedelectronica.es/dossier` | eHome catálogo | Informativo licencias |
| SITCM WFS | `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO` | GeoJSON WFS | Geometría ámbitos planeamiento (33 polígonos) |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress Ganesa)

- **URL:** `https://manzanareselreal.es/ordenacion-del-territorio/urbanismo/`
- **API REST:** `https://manzanareselreal.es/wp-json/wp/v2/posts?categories=41`
- **Contenido:** Noticias de PGOU (información pública 2026), obras viales, licitaciones infraestructura.
- **Mecanismo:** Posts WP con categoría Urbanismo; enlaces a sede transparencia para documentación PGOU.

### 2. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://manzanareselreal.sedelectronica.es/board`
- **Formato:** Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Ejemplos (jul 2026):** PGOU aprobación inicial (exp. 597/2026), expediente de dominio parcela Pedriza.
- **Limitación:** Certificado SSL cadena incompleta → `insecure_ssl: true`. Solo anuncios vigentes (~10 filas).

### 3. Portal de transparencia — Normativa urbanística

- **URL:** `https://manzanareselreal.sedelectronica.es/transparency/70fa3e9b-9aec-443a-9c20-882f0ecd03df/`
- **Documentos:** NNSS, planes parciales (P. 11 Las Rocas, P. 12 Peña El Gato, P. 13 La Ponderosa, P. 16 El Rincón), ordenanzas edificación y arbolado.

### 4. Sede electrónica — Trámites y expedientes

- **Catálogo trámites:** `/dossier` — solicitud licencia urbanística, consulta expedientes.
- **Consulta expedientes:** `/expedientes` — requiere Cl@ve/certificado.

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| Gobierno abierto (`gobiernoabierto.manzanareselreal.es`) | Sin listado expedientes urbanísticos estructurado |
| BOCM re-parse | Ya cubierto en pipeline regional |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDEM Comunidad de Madrid: `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='MANZANARES EL REAL'` (33 ámbitos: P-1 … P-29B).
  - Códigos plan parcial en transparencia (P. 11, P. 12, …) enlazan con `DS_NOMB_AMB` (P-11, P-12, …).
- **Estrategia:** Cargar todos los ámbitos SIT como proyectos con polígono; enriquecer tablón/dossier por código P-XX o ILIKE sobre nombre sector.
- **Limitaciones:** Tablón y licencias sin geometría propia; WFS no enlaza expediente administrativo (solo ámbito planeamiento). Sin visor ArcGIS municipal propio.

## Estrategia de ingesta

- **proyectos.jsonl:** Dossier normativa + tablón sede + posts WP urbanismo + ámbitos SIT WFS + servicio PGOU.
- **licencias.jsonl:** Páginas informativas (urbanismo + sede) + tablón filtrado.
- **IDs:** `manzanares-el-real-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (normativa + SIT + tablón + noticias).
- `licencias`: partial (trámites informativos; pocas concesiones en tablón).
- `with_geometry`: >0 vía SIT WFS (ámbitos planeamiento).
