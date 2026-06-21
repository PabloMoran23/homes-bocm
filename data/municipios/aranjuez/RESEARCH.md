# Aranjuez — investigación portal ayuntamiento

**Slug:** `aranjuez`  
**BOCM (referencia):** 44 anuncios  
**Fecha investigación:** 2026-06-20

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (WordPress) | https://www.aranjuez.es | Accesible |
| Sede electrónica (STA) | https://sede.aranjuez.es | Accesible |
| Tablón virtual sede | `/portal/noEstatica.do?opc_id=10008` | Redirige al tablón WP (en fase de pruebas) |

## Fuentes de datos

### 1. Tablón de Edictos (principal)

- **URL:** https://www.aranjuez.es/tablon-de-edictos/
- **Formato:** WordPress (Elementor), listas `<h3>` por departamento + `<li><a href="...pdf">`.
- **Secciones:** Contratación, Hacienda, Personal, Policía Local, Secretaría, **Urbanismo**, Medio Ambiente, Censo Electoral.
- **Contenido urbanístico:** Anuncios de licencias de actividad/obra publicados en tablón (PDF en `/wp-content/uploads/`).
- **Fechas:** Prefijo `DD/MM/YYYY.` en el texto del enlace.
- **Limitación:** Solo edictos vigentes (~25 ítems totales); sin histórico paginado.

### 2. Concejalía de Urbanismo — planeamiento

- **Raíz:** https://www.aranjuez.es/concejalias/urbanismo/
- **Subpáginas:** PGOU1996, normativa técnica, sectores (La Montaña, Ciudad de las Artes, Puente Largo, Cerro de la Linterna), obras acceso norte, cartografía.
- **Formato:** WordPress con PDFs en `/images/files/urbanismo/` y ocasionalmente `/wp-content/uploads/`.
- **Contenido:** Normas PGOU 1996, planes parciales, ordenanzas sectoriales, instrucciones urbanísticas.
- **Uso:** Proyectos de planeamiento (`tipo`: PGOU, plan parcial, normativa urbanística).

### 3. Sede electrónica — trámites (informativo)

- **URL:** https://sede.aranjuez.es/sede/catalogoTramites.do (SERVICIOS TÉCNICOS/URBANISMO)
- **Modelos:** 191 (obra no vinculada), 193 (obra vinculada actividad), 195 (escasa entidad), etc.
- **Limitación:** Catálogo de trámites y formularios PDF; no publica concesiones ni listado de expedientes. No se ingiere como licencia concedida.

### 4. Solicitudes OAC

- **URL:** https://www.aranjuez.es/solicitudes/ (sección Servicios Técnicos / Urbanismo)
- **Formato:** Listado de modelos normalizados descargables.
- **Limitación:** Trámites informativos; no concesiones publicadas.

## Estrategia de ingesta

| Dataset | Fuente principal | Secundaria |
|---------|------------------|------------|
| `licencias.jsonl` | Tablón de Edictos (sección Urbanismo + regex licencia) | — |
| `proyectos.jsonl` | Páginas urbanismo (PGOU, sectores, normativa) | Tablón (edictos urbanísticos) |

IDs estables: `aranjuez-{lic|proy}-{sha256[:14]}`.

## Limitaciones conocidas

- Sin API JSON ni datos abiertos georreferenciados de licencias.
- Tablón virtual de la sede en fase de pruebas; redirige al tablón WordPress.
- Sin coordenadas ni distrito en fuentes del ayuntamiento (`lat`/`lon` = null).
- El tablón muestra solo anuncios vigentes, no archivo histórico completo.
- PDFs de planeamiento suelen carecer de fecha explícita (se infiere del nombre/URL o año en filename).
