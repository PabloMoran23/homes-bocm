# El Boalo-Cerceda-Mataelpino — investigación portal ayuntamiento

**Slug:** `el-boalo-cerceda-mataelpino`  
**Nombre oficial:** El Boalo-Cerceda-Mataelpino (Ayuntamiento de El Boalo, Cerceda y Mataelpino)  
**BOCM (referencia):** 3 anuncios  
**Fecha investigación:** 2026-08-17

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (WordPress/Elementor) | https://elboalo-cerceda-mataelpino.org | Accesible |
| Sede electrónica (add4u/GestDoc, eAdmin) | https://sede.elboalo-cerceda-mataelpino.org/eAdmin | Accesible (SSL caducado — `sede_insecure_ssl`) |
| Sede espublico gestiona | https://elboalo.sedelectronica.es | Accesible |
| Dominios legacy | https://www.elboalo.es, https://elboalo.es | No resuelven |

## Fuentes de datos

### 1. Normativa urbanística (WordPress)

- **URL:** https://elboalo-cerceda-mataelpino.org/normativa-urbanistica/
- **Formato:** WordPress/Elementor con enlaces directos a PDF en `/wp-content/uploads/`.
- **Contenido:** PGOU (Normas Subsidiarias BOCM 174/2011), planos de ordenación (El Boalo, Cerceda, Mataelpino), ordenanzas urbanísticas.
- **Uso:** `proyectos.jsonl` (planeamiento, PGOU, documento urbanismo).

### 2. Área Urbanismo (WordPress)

- **URL:** https://elboalo-cerceda-mataelpino.org/urbanismo/
- **Formato:** Página Elementor con trámites enlazados a `elboalo.sedelectronica.es` (URLs firmadas dinámicas).
- **Uso:** `licencias.jsonl` (trámites informativos) + contexto urbanístico.

### 3. Tablón de anuncios (sede add4u)

- **URL:** https://sede.elboalo-cerceda-mataelpino.org/eAdmin/Tablon.do?action=verAnuncios
- **Búsqueda:** POST `referenciaBusqueda=<término>` al mismo endpoint.
- **Estado (2026-08-17):** Secciones vacías; parser preparado para cuando haya filas.

### 4. Tablón espublico gestiona

- **URL:** https://elboalo.sedelectronica.es/board
- **Formato:** HTML tabla con `preview-document/<uuid>` por fila.
- **Contenido:** Bandos, avisos, tarifas; sin edictos urbanísticos recientes (2026-08-17).
- **Uso:** licencias/proyectos cuando aparezcan anuncios urbanísticos.

### 5. Noticias municipales (WordPress REST)

- **API:** https://elboalo-cerceda-mataelpino.org/wp-json/wp/v2/posts
- **Ejemplos urbanísticos:** subasta parcelas Cerceda, cortes M-607 por obras, gymkhana urbana.
- **Uso:** `proyectos.jsonl` filtrando título con palabras clave urbanísticas (excluye obras de teatro).

### 6. Portal de transparencia

- **URL WP:** https://elboalo-cerceda-mataelpino.org/portal-de-transparencia/
- **URL sede:** https://elboalo.sedelectronica.es/transparency
- **Limitación:** Sin visor de expedientes urbanísticos georreferenciado.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='EL BOALO'`
  - Visor: https://www.madrid.org/cartografia/sitcm/html/visor.htm
- **Estrategia:** Descarga de 113 ámbitos SITCM como filas `proyectos.jsonl` (`origen: sit_wfs`) con polígono WGS84; enriquecimiento por código de ámbito (S-*, UE-*, POLÍGONO *) en títulos de tablón/noticias.
- **Limitaciones:**
  - Tablón/PDF sin enlace GIS directo al expediente.
  - Geometría solo para ámbitos de planeamiento SITCM, no para licencias individuales.
  - Certificado SSL caducado en sede add4u.

## Estrategia de ingesta

| Dataset | Fuente principal | Secundaria |
|---------|------------------|------------|
| `proyectos.jsonl` | SITCM WFS (ámbitos) + normativa urbanística (PDFs) | WP posts + tablones |
| `licencias.jsonl` | Tablones (cuando haya edictos) | Ordenanza licencias + trámites WP |

IDs estables: `el-boalo-cerceda-mataelpino-{lic|proy}-{sha256[:14]}`.

## Limitaciones conocidas

- Tablón add4u vacío; espublico sin edictos urbanísticos en el momento de la investigación.
- Sin API JSON de licencias concedidas ni coordenadas/distrito por expediente.
- Trámites en `elboalo.sedelectronica.es` usan URLs firmadas no deterministas.
