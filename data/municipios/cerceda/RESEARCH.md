# Cerceda — investigación portal ayuntamiento

**Slug:** `cerceda`  
**Nombre oficial:** Cerceda (localidad del Ayuntamiento de El Boalo, Cerceda y Mataelpino)  
**Provincia:** Madrid  
**Comunidad autónoma:** Comunidad de Madrid  
**BOCM (referencia):** 1 anuncio  
**Fecha investigación:** 2026-09-12

## Nota territorial

Cerceda **no es un municipio independiente**: es una de las tres localidades del término municipal de El Boalo, Cerceda y Mataelpino (Sierra Norte de Madrid). El portal oficial es el del ayuntamiento conjunto.

**Atención:** `www.cerceda.es` redirige a `www.cerceda.org` (Concello de Cerceda, A Coruña, Galicia) — **no** corresponde a esta localidad madrileña.

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (WordPress/Elementor) | https://elboalo-cerceda-mataelpino.org | Accesible |
| Sede electrónica (add4u/GestDoc, eAdmin) | https://sede.elboalo-cerceda-mataelpino.org/eAdmin | Accesible (SSL caducado — `sede_insecure_ssl`) |
| Sede alternativa (espublico gestiona) | https://elboalo.sedelectronica.es | Accesible |
| Dominio erróneo (Galicia) | https://www.cerceda.es → cerceda.org | No usar |

## Fuentes de datos

### 1. Normativa urbanística (WordPress)

- **URL:** https://elboalo-cerceda-mataelpino.org/normativa-urbanistica/
- **Formato:** WordPress/Elementor con enlaces directos a PDF en `/wp-content/uploads/`.
- **Contenido relevante para Cerceda:**
  - PGOU (Normas Subsidiarias BOCM 174/2011) — municipio completo
  - **Plano de Ordenación Cerceda** (`Plano-Ordenacion-Cerceda.pdf`)
  - Ordenanzas urbanísticas (vehículos, ocupación vía pública, régimen de licencias) — municipio completo
- **Uso:** `proyectos.jsonl` (planeamiento Cerceda + normativa compartida).

### 2. Área Urbanismo (WordPress)

- **URL:** https://elboalo-cerceda-mataelpino.org/urbanismo/
- **Contenido:** Trámites de licencia, declaración responsable, certificados urbanísticos.
- **Limitación:** Enlaces a sede espublico con tokens dinámicos no estables.

### 3. Tablón de anuncios (sede add4u)

- **URL:** https://sede.elboalo-cerceda-mataelpino.org/eAdmin/Tablon.do?action=verAnuncios
- **Búsqueda:** POST `referenciaBusqueda=<término>` (incluye `cerceda`, `urbanismo`, `licencia`, etc.)
- **Estado (2026-09-12):** Secciones vacías. Parser implementado para cuando haya filas.

### 4. Tablón espublico

- **URL:** https://elboalo.sedelectronica.es/board
- **Estado:** Sin edictos urbanísticos visibles en el momento de la investigación.

### 5. Noticias municipales (WordPress REST)

- **API:** https://elboalo-cerceda-mataelpino.org/wp-json/wp/v2/posts?search=cerceda
- **Ejemplos urbanísticos:** «Venta de Parcelas Municipales mediante Subasta Pública en Cerceda» (2026-09-01).
- **Uso:** `proyectos.jsonl` filtrando título/contenido con «Cerceda» + palabras clave urbanísticas.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='EL BOALO'` (cubre El Boalo, Cerceda y Mataelpino)
  - Visor: https://www.madrid.org/cartografia/sitcm/html/visor.htm
- **Estrategia:** Descarga de ámbitos SITCM como filas `proyectos.jsonl` (`origen: sit_wfs`) con polígono WGS84; enriquecimiento por código de ámbito en títulos.
- **Limitaciones:**
  - Geometría a nivel de ámbito de planeamiento del municipio conjunto, no delimitación de la localidad Cerceda.
  - Plano Ordenación Cerceda es PDF sin georreferenciación vectorial enlazable.
  - Tablón/PDF sin enlace GIS directo al expediente.
  - Certificado SSL caducado en sede add4u.

## Estrategia de ingesta

| Dataset | Fuente principal | Secundaria |
|---------|------------------|------------|
| `proyectos.jsonl` | SITCM WFS (ámbitos) + normativa (PGOU/plano Cerceda) | WP posts Cerceda + tablón |
| `licencias.jsonl` | Tablón sede (cuando haya edictos) | Ordenanza licencias + trámites WP |

IDs estables: `cerceda-{lic|proy}-{sha256[:14]}`.

## Limitaciones conocidas

- Portal compartido con El Boalo y Mataelpino; filtro por localidad en noticias.
- Tablón digital vacío en el momento de la investigación.
- Sin API JSON de licencias concedidas ni coordenadas/distrito por expediente.
- `cerceda.es` apunta a Galicia (confusión de dominios).
