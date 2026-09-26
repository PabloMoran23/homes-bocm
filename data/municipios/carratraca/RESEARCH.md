# Carratraca — investigación portal ayuntamiento

**Municipio:** Carratraca (Málaga, Andalucía)  
**Slug:** `carratraca`  
**INE:** 29039  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.carratraca.es | **Bloqueada** — CloudFront 403 en CI |
| Sede electrónica | https://carratraca.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://carratraca.sedelectronica.es/board/ | **Operativa** — tabla HTML Wicket (~4 filas) |
| Portal transparencia | https://carratraca.sedelectronica.es/transparency | **Operativa** — sección 7. URBANISMO (180 docs, AJAX) |
| Catálogo trámites | https://carratraca.sedelectronica.es/dossier | Redirige; sin listado histórico |
| Consulta expedientes | https://carratraca.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Declaración responsable obras | https://www.carratraca.es/12507/solicitud-de-obras-u-ocupacion-por-declaracion-responsable | Bloqueada (403) en CI; PDFs en `/subidas/archivos/` |
| PGOU BOJA aprobación definitiva | https://www.juntadeandalucia.es/boja/2025/200/55 | **Operativa** — EM-CR-3 (22-sep-2025) |
| PGOU BOJA aprobación inicial | https://www.juntadeandalucia.es/boja/2017/200/81 | **Operativa** — PP. 2940/2017 |
| Diputación Málaga planeamiento | http://www.malaga.es/fomentoinfraestructuras/planeamiento/ficha.asp?mun=29039 | Intermitente (403 en CI) |
| SITUA (Junta de Andalucía) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cártama, Alcaucín, Coín.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Contenido actual (sep 2026):** solo anuncios administrativos (censo electoral, convocatoria pleno, cifras de electores). Sin licencias ni planeamiento en primera página.

## Planeamiento / PGOU

- **Primer PGOU** del municipio; tramitación desde 2017.
- **Aprobación definitiva** CTOTU Málaga: 22-sep-2025 (expediente EM-CR-3), publicada en BOJA 10-oct-2025.
- **Sectores** referenciados en BOJA 2017: SUS-1 a SUS-4, SUS-IND, SUS-H1, SUS-H2.
- Documentación PGOU también en sede electrónica durante información pública (2017).
- Portal transparencia: sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (~180 documentos); subcarpetas requieren Wicket AJAX (redirige a login al intentar navegar sin sesión).

## Licencias de obra

- No hay dataset público de concesiones históricas.
- **Declaración responsable** de obras y ocupación vía pública: formularios PDF en web municipal.
- Trámites de urbanismo en catálogo sede (`Urbanismo y Vivienda`); sin listado público de licencias concedidas.
- Las licencias publicadas aparecerían en el tablón como edictos (actualmente sin entradas urbanísticas).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): planeamiento por municipio, sin campo expediente del tablón municipal.
  - PRP Málaga / Diputación: visor cartográfico provincial (`gis.prpmalaga.es`); sin REST accesible desde CI.
  - No hay visor urbanístico municipal ni WFS/GeoJSON por expediente.
- **Estrategia:** documentos del tablón y transparencia son PDF sin georreferencia; PGOU en BOJA/SITUA sin enlace por código de expediente del ayuntamiento.
- **Limitaciones:**
  - Web municipal bloqueada impide extraer visores desde CMS.
  - Transparencia urbanismo requiere sesión AJAX.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Web `carratraca.es` no scrapeable (CloudFront WAF).
- Tablón con pocos anuncios administrativos; sin licencias urbanísticas publicadas actualmente.
- Transparencia: árbol de 180 docs requiere sesión Wicket.
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.carratraca:CarratracaAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas (trámites, formularios DR) + metadatos PGOU (BOJA, SITUA, Diputación).
- IDs: `carratraca-lic-*` / `carratraca-proy-*` (sha256[:14]).
