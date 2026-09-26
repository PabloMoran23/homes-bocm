# Fuente de Piedra — investigación portal ayuntamiento

**Municipio:** Fuente de Piedra (Málaga, Andalucía)  
**Slug:** `fuente-de-piedra`  
**INE:** 29055  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.fuentedepiedra.es | **Bloqueada** — CloudFront 403 desde CI (plataforma Diputación Málaga) |
| Sede electrónica | https://fuentedepiedra.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://fuentedepiedra.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://fuentedepiedra.sedelectronica.es/dossier | Requiere sesión previa (cookie del tablón); redirect loop sin warm-up |
| Urbanismo y Vivienda (sede) | https://fuentedepiedra.sedelectronica.es/catalog/t/a4806ac2-0236-4222-9c47-52bdaaa42c9e | Catálogo trámites urbanismo (UUID compartido espublico) |
| Normativa municipal | https://fuentedepiedra.sedelectronica.es/normative | Listado normativa en sede |
| Transparencia | https://fuentedepiedra.sedelectronica.es/transparency | Portal transparencia sede |
| Consulta expedientes | https://fuentedepiedra.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| PGOU (web) | https://www.fuentedepiedra.es/9375/pgou | Enlace a documentación PGOU (403 en CI) |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Consulta instrumentos de planeamiento autonómicos |
| VITUA | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ | Visor cartográfico urbanístico Junta de Andalucía |
| PGOU BOJA 2011 | https://www.juntadeandalucia.es/boja/2011/246/d24.pdf | Aprobación definitiva PGOU (registro autonómico 4950) |
| Mod. PGOU BOJA 2022 | https://www.juntadeandalucia.es/boja/2022/133/BOJA22-133-00013-11534-01_00264813.pdf | Modificación ámbito urbano (exp. EM-FTP-21) |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Alcaucín, Cómpeta, Coín.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas estándar espublico.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Estado sep 2026:** 4 anuncios activos, ninguno urbanístico (presupuestos, jurado, vacaciones alcaldía).

### Ejemplos en tablón (sep 2026)

| Fecha | Procedimiento | Descripción |
|-------|---------------|-------------|
| 09/09/2026 | Modificaciones Presupuestarias | Suplemento de crédito |
| 07/09/2026 | Procedimiento Genérico | Ley del Tribunal del Jurado |
| 31/08/2026 | Vacaciones | Ausencia de alcaldía |
| 19/12/2024 | Procedimiento Genérico | Sorteo bienal miembros jurado |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites disponibles en sede (`/dossier`): Licencia Urbanística, Licencia de Ocupación, Licencia de Actividad, Obras de Urbanización, etc.
- Catálogo «Urbanismo y Vivienda» en sede.
- Las concesiones publicadas aparecen en el tablón como edictos (cuando existan).

## Proyectos / planeamiento

- **PGOU vigente:** aprobado definitivamente 27/07/2011 (BOJA 246/2011); modificación parcial ámbito urbano 20/06/2022 (BOJA 133/2022).
- **Web municipal:** página PGOU con enlace a documentación (inaccesible desde CI).
- **SITUA/VITUA:** consulta de instrumentos y zonificación; sin enlace a expedientes del tablón.
- **Tablón:** sin anuncios de información pública urbanística en el momento de la investigación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): visor de zonificación PGOU por municipio (INE 29055); sin campo de enlace a expediente del tablón.
  - SITUA: documentación alfanumérica de planeamiento; sin geometría por código de expediente.
  - PRP Málaga (`gis.prpmalaga.es`): visores provinciales; malaga.es bloqueado CloudFront desde CI.
- **Estrategia:** los visores autonómicos/provinciales muestran zonificación PGOU, **sin campo de enlace a expediente** del tablón. Los anuncios son PDF sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST enlazable por código de expediente.
  - Web municipal con WAF CloudFront.
  - El orquestador aplicará centroide municipio (37.135, -4.73) + jitter.

## Limitaciones generales

- Tablón sin entradas urbanísticas en el momento de la investigación.
- Web municipal bloqueada en CI (403 CloudFront).
- `/dossier` requiere warm-up de sesión (cookie JSESSIONID del tablón).
- Consulta de expedientes requiere login.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.fuente_de_piedra:FuenteDePiedraAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas de trámites (sede) + PGOU/BOJA/SITUA/VITUA estáticos.
