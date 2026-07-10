# Chapinería — investigación portal ayuntamiento

**Slug:** `chapineria`  
**Nombre oficial:** Chapinería  
**BOCM (referencia):** 14 anuncios  
**Fecha investigación:** 2026-07-10

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (WordPress TownPress) | https://chapineria.madrid | Accesible |
| Sede electrónica (espublico gestiona) | https://chapineria.sedelectronica.es | Accesible (`insecure_ssl` en sede) |
| Visor SIT Comunidad de Madrid | https://idem.madrid.org/cartografia/sitcm/html/visor.htm | Accesible (enlace desde urbanismo) |

## Fuentes de datos

### 1. Urbanismo (WordPress)

- **Página:** https://chapineria.madrid/urbanismo/
- **Formato:** WPBakery; texto informativo + botones a modelos formalizados y visor SITCM (NNSS).
- **Normativa:** Normas Subsidiarias de Planeamiento (BOCM 11-jul-2000); sin PGOU municipal propio publicado en web.
- **Uso:** página semilla; enlace al visor SIT.

### 2. Área de descargas — formularios urbanismo

- **URL:** https://chapineria.madrid/area-de-descargas/
- **Serie 04.xx:** modelos de licencia, declaración responsable, cédula urbanística, parcelación, gestión urbanística, etc.
- **Formato:** enlaces directos a `/wp-content/uploads/*.pdf`.
- **Uso:** `licencias.jsonl` como trámites informativos (no concesiones publicadas).

### 3. Tablón sede electrónica (espublico)

- **URL:** https://chapineria.sedelectronica.es/board
- **Formato:** tabla HTML con `preview-document/{uuid}`; columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
- **Estado (2026-07-10):** 5 anuncios recientes (empleo, bando parcelas/incendios, ordenanza fiscal BOCM); sin filas de categoría «Urbanismo» en el scrape.
- **Consulta expedientes:** `/expedientes` requiere Cl@ve; sin listado público.

### 4. Noticias WordPress

- Búsqueda REST `search=urbanismo` / `search=parcela`: sin entradas urbanísticas relevantes (solo noticia licencia taxi).
- Sin categoría «tablón municipal» dedicada como en otros municipios CM.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer CM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='CHAPINERÍA'`
  - Campo ámbito: `DS_NOMB_AMB`
  - Visor SITCM: enlace desde página urbanismo
- **Ámbitos (35):** UE-01…UE-25, UE-V 01 VALQUIGOSO, S-01…S-10 (suelo rústico)
- **Estrategia:** descarga WFS `srsName=EPSG:4326`; un registro `proyectos.jsonl` por ámbito NNSS con polígono; emparejamiento heurístico título ↔ `DS_NOMB_AMB` en anuncios del tablón.
- **Limitaciones:** tablón/PDF sin código UE en la mayoría de anuncios; licencias sin polígono; visor SIT no enlaza expediente individual.

## Estrategia de ingesta

| Dataset | Fuente principal | Secundaria |
|---------|------------------|------------|
| `proyectos.jsonl` | WFS SIT ámbitos NNSS (35) | Tablón sede (bando parcelas, BOCM) |
| `licencias.jsonl` | Formularios 04.xx (área descargas) | Tablón sede + páginas informativas |

IDs estables: `chapineria-{lic|proy}-{sha256[:14]}`.

## Limitaciones conocidas

- Tablón sede con pocos anuncios y sin licencias urbanísticas indexadas en HTML estático.
- Sin dataset público de licencias concedidas con coordenadas.
- Geometría SIT aplica a ámbitos de planeamiento (NNSS 2000), no a expedientes puntuales.
- Sede espublico: certificado TLS inválido en algunos entornos (`insecure_ssl: true`).
