# Torrejón de Ardoz — investigación portal ayuntamiento

**Slug:** `torrejon-de-ardoz`  
**BOCM (referencia):** 149 anuncios  
**Fecha investigación:** 2026-06-17

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (Drupal 10) | https://www.ayto-torrejon.es | Accesible |
| Sede electrónica (STA / tablón virtual) | https://sede.ayto-torrejon.es | Accesible |
| Dominio legacy | https://www.torrejondeardoz.es | 500/403 — no usar |

## Fuentes de datos

### 1. Tablón virtual — Urbanismo (`TABURB`)

- **URL:** `https://sede.ayto-torrejon.es/portal/tablonVirtual.do?subseccion=TABURB&opc_id=175&ent_id=1&idioma=1`
- **Formato:** HTML con tabla `Lista2` (7 columnas: año, código, tipo, nombre, fecha creación, fecha publicación, estado).
- **Contenido:** Expedientes urbanísticos publicados (licencias calificadas/inocuas, edictos). Cada fila enlaza a detalle `?expId=<id>`.
- **Detalle expediente:** Metadatos + tabla de documentos firmados (`documento=<id>&codVerif=...`). Los PDFs requieren sesión/código de verificación; se usa la URL de detalle como `url` y el nombre del documento como título auxiliar.
- **Licencias:** Tipos `URB_LICENCIAS DE ACTIVIDADES CALIFICADAS`, `URB_LICENCIAS DE ACTIVIDADES INOCUAS`, y similares con prefijo `URB_` + `LICENCIA`.
- **Limitación:** Solo expedientes actualmente publicados en el tablón (sin histórico completo ni paginación visible). Sin coordenadas ni distrito.

### 2. Tablón virtual — Información (`INFOTAB`)

- **URL:** `https://sede.ayto-torrejon.es/portal/tablonVirtual.do?subseccion=INFOTAB&opc_id=175&ent_id=1&idioma=1`
- **Formato:** Misma tabla HTML que TABURB.
- **Contenido:** Edictos y anuncios generales; se filtran filas con palabras clave urbanísticas (expediente, parcela, finca, urbanismo, etc.).

### 3. Drupal — Ordenanzas y normativa urbanística

- **URL:** `https://www.ayto-torrejon.es/concejalias/urbanismo/ordenanzas-y-normativa`
- **Formato:** Drupal 10, enlaces a PDFs en `/sites/default/files/`.
- **Contenido:** Planes especiales, modificaciones PGOU, anuncios de aprobación inicial/definitiva, plano oficial.
- **Uso:** Proyectos de planeamiento (`tipo`: plan especial, PGOU, documento urbanismo).

### 4. Trámites urbanismo (informativo)

- **URL:** `https://www.ayto-torrejon.es/concejalias/urbanismo/tramites`
- **Formato:** Listado Drupal de trámites (licencia de obra, declaración responsable, etc.).
- **Limitación:** No publica concesiones ni expedientes; solo descripción de trámites. No se ingiere como licencia concedida.

## Estrategia de ingesta

| Dataset | Fuente principal | Secundaria |
|---------|------------------|------------|
| `licencias.jsonl` | TABURB (tipos URB_*LICENCIA*) | — |
| `proyectos.jsonl` | TABURB + INFOTAB (expedientes) | Drupal ordenanzas PDFs |

IDs estables: `torrejon-de-ardoz-{lic|proy}-{sha256[:14]}`.

## Limitaciones conocidas

- Sin API JSON ni datos abiertos georreferenciados de licencias.
- PDFs del tablón virtual requieren código de verificación; no se descargan en el scrape.
- El tablón muestra un subconjunto reciente de expedientes (no archivo histórico completo).
- `www.torrejondeardoz.es` no resuelve de forma fiable; usar `ayto-torrejon.es`.
