# El Boalo — investigación portal ayuntamiento

**Slug:** `el-boalo`  
**Nombre oficial:** El Boalo (Ayuntamiento de El Boalo, Cerceda y Mataelpino)  
**BOCM (referencia):** 39 anuncios  
**Fecha investigación:** 2026-06-21

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (WordPress/Elementor) | https://elboalo-cerceda-mataelpino.org | Accesible |
| Sede electrónica (add4u/GestDoc, eAdmin) | https://sede.elboalo-cerceda-mataelpino.org/eAdmin | Accesible (SSL caducado — `insecure_ssl`) |
| Sede alternativa (espublico gestiona) | https://elboalo.sedelectronica.es | Accesible |
| Dominios legacy | https://www.elboalo.es, https://elboalo.es | No resuelven |

## Fuentes de datos

### 1. Normativa urbanística (WordPress)

- **URL:** https://elboalo-cerceda-mataelpino.org/normativa-urbanistica/
- **Formato:** WordPress/Elementor con enlaces directos a PDF en `/wp-content/uploads/`.
- **Contenido:** PGOU (Normas Subsidiarias BOCM 174/2011), planos de ordenación (El Boalo, Cerceda, Mataelpino), ordenanzas urbanísticas (vehículos, ocupación vía pública, régimen de licencias).
- **Uso:** `proyectos.jsonl` (planeamiento, PGOU, documento urbanismo). La ordenanza de licencias también alimenta `licencias.jsonl` como trámite informativo.

### 2. Área Urbanismo (WordPress)

- **URL:** https://elboalo-cerceda-mataelpino.org/urbanismo/
- **Formato:** Página Elementor con trámites enlazados a `elboalo.sedelectronica.es` (URLs firmadas dinámicas) y noticias municipales de obras/planificación.
- **Contenido:** Declaración responsable, solicitud de licencia, certificados urbanísticos, modificación/aprobación de planeamiento.
- **Limitación:** Los enlaces a trámites de la sede espublico llevan token `?x=...` no estable; se usan las páginas WP y normativa como fuentes estables.

### 3. Tablón de anuncios (sede add4u)

- **URL:** https://sede.elboalo-cerceda-mataelpino.org/eAdmin/Tablon.do?action=verAnuncios
- **Búsqueda:** POST `referenciaBusqueda=<término>` al mismo endpoint.
- **Formato:** HTML con secciones (Anuncios, Bandos, Edictos, Multas). Cada sección usa tablas Bootstrap cuando hay contenido.
- **Estado (2026-06-21):** Todas las secciones vacías («Actualmente, no existen anuncios»). El scrape implementa parsing para cuando haya filas + búsqueda por términos urbanísticos.
- **Uso:** licencias (edictos/solicitudes) y proyectos (información pública, edictos).

### 4. Noticias municipales (WordPress REST)

- **API:** https://elboalo-cerceda-mataelpino.org/wp-json/wp/v2/posts
- **Ejemplos urbanísticos:** subasta parcelas Cerceda, bando desbroce parcelas, planes de asfaltado/embellecimiento, subvenciones urbanizaciones.
- **Uso:** `proyectos.jsonl` filtrando título/contenido con palabras clave urbanísticas.

### 5. Portal de transparencia

- **URL WP:** https://elboalo-cerceda-mataelpino.org/portal-de-transparencia/
- **URL sede espublico:** https://elboalo.sedelectronica.es/transparency
- **Limitación:** Secciones genéricas LOPDGDD; sin visor de expedientes urbanísticos georreferenciado.

## Estrategia de ingesta

| Dataset | Fuente principal | Secundaria |
|---------|------------------|------------|
| `proyectos.jsonl` | Normativa urbanística (PDFs PGOU/planos) | WP posts + tablón sede |
| `licencias.jsonl` | Tablón sede (cuando haya edictos) | Ordenanza licencias + trámites WP |

IDs estables: `el-boalo-{lic|proy}-{sha256[:14]}`.

## Limitaciones conocidas

- Tablón digital vacío en el momento de la investigación; histórico no expuesto.
- Sin API JSON de licencias concedidas ni coordenadas/distrito.
- Certificado SSL de `sede.elboalo-cerceda-mataelpino.org` inválido; scrape con verificación desactivada.
- Trámites en `elboalo.sedelectronica.es` usan URLs firmadas no deterministas.
- No replicar pipeline Madrid capital (`sector_geometry/madrid_*`).
