# Alfarnate — investigación portal ayuntamiento

**Municipio:** Alfarnate (Málaga, Andalucía)  
**Slug:** `alfarnate`  
**INE:** 29007  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.alfarnate.es | **Operativa** — plataforma Diputación Málaga (`static.malaga.es/municipios`) |
| Portada ES | https://www.alfarnate.es/es | OK con UA navegador; rate-limit ocasional (HTTP 202 vacío) |
| PGOU | https://www.alfarnate.es/3253/pgou-alfarnate | Página informativa PGOU |
| Urbanismo | https://www.alfarnate.es/14578/com1_md1_cd-18748/urbanismo | Concejalía y documentación |
| Licencias | https://www.alfarnate.es/14578/com1_md1_cd-18746/licencias-y-permisos-municipales | Trámites informativos |
| Trámites en línea | https://www.alfarnate.es/3263/tramites-en-linea | Enlace a sede Diputación |
| Ordenanza (IP) | https://www.alfarnate.es/81/com1_md3_cd-70655/publicacion-texto-del-proyecto-de-ordenanza | Publicación proyecto ordenanza |
| Sede local | https://alfarnate.sedelectronica.es | **Inactiva** — mensaje «Sede Electrónica temporalmente inactiva» |
| Tablón sede local | https://alfarnate.sedelectronica.es/board/ | Inactiva (misma página) |
| Sede Diputación | https://sede.malaga.es/alfarnate | Sede centralizada; timeout/WAF en CI |
| Gobierno abierto | https://www.malaga.es/gobiernoabierto/alfarnate | Portal transparencia Diputación (ent=729); AWS WAF en CI |
| Planeamiento Diputación | https://www.malaga.es/delegacionfomento/planeamiento/ficha.asp?mun=29003&cod=736 | Ficha PGOU Alfarnate |

## CMS y listado de expedientes

- **Web municipal:** CMS Diputación de Málaga (ASPSOPDE + plantilla municipios). Contenidos estáticos por sección (`/3253/`, `/14578/`, noticias `/81/...`).
- **Sede local:** espublico gestiona, pero **inactiva** en septiembre 2026.
- **Sede centralizada:** Diputación de Málaga (`sede.malaga.es/alfarnate`) para trámites; sin tablón público scrapeable desde CI.
- **No hay** visor de expedientes urbanísticos ni API JSON pública en la web municipal.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Página «Licencias y permisos municipales» con información y modelos.
- Trámites vía sede Diputación (`sede.malaga.es/alfarnate`).
- Tablón local inactivo; sin edictos scrapeables actualmente.

## Proyectos / planeamiento

- **PGOU** aprobado definitivamente 2011 (expediente EM-AF-2, BOJA 101/2011).
- **Innovación PGOU** 2023 (sectores UR-1/UR-2, campo de fútbol; expediente EM-AF-4, BOJA 2024/35).
- Documentación en web municipal (PGOU, urbanismo) y ficha Diputación (`mun=29003`, `cod=736`).
- Publicación de proyecto de ordenanza en noticias municipales.
- Gobierno abierto Diputación incluye sección «Información urbanística» y documentos PGOU.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): planeamiento autonómico; sin enlace a expedientes del ayuntamiento.
  - PRP Málaga / `gis.prpmalaga.es`: visores cartográficos provinciales; sin REST por código de expediente.
  - Ficha planeamiento Diputación: documentación alfanumérica/PDF, sin geometría por expediente.
  - Observatorio mapas gobierno abierto (`malaga.es/gobiernoabierto/observatorio/mapas/`): WAF AWS; no enlazable a expedientes.
- **Estrategia:** sin visor municipal ni WFS público enlazable; el orquestador aplica centroide municipio + jitter.
- **Limitaciones:**
  - Sede local inactiva; sin tablón scrapeable.
  - `malaga.es` protegido con AWS WAF (challenge JS) desde entornos automatizados.
  - Rate-limit intermitente en `alfarnate.es` (respuestas HTTP 202 vacías).

## Limitaciones generales

- Sin listado histórico público de licencias concedidas.
- Sede local inactiva; dependencia de sede centralizada Diputación.
- WAF/rate-limit en fuentes Diputación y web municipal desde CI.

## Adapter implementado

- `municipio.adapters.alfarnate:AlfarnateAyuntamientoAdapter`
- Fuentes: páginas estáticas PGOU/urbanismo/ordenanza + crawl semillas web + intento tablón sede local (vacío si inactiva).
