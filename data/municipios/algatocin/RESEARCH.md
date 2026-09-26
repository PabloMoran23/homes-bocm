# Algatocín — investigación portal ayuntamiento

**Municipio:** Algatocín (Málaga, Andalucía)  
**Slug:** `algatocin`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.algatocin.es | **Operativa** con UA navegador; CloudFront 403 sin UA |
| Sede electrónica | https://algatocin.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://algatocin.sedelectronica.es/board/ | **Operativa** — tabla HTML Wicket (~6 filas) |
| Consulta pública previa | https://algatocin.sedelectronica.es/transparency/74eefec2-abd4-4c14-be2f-20f83913f444/ | Vacía actualmente |
| Información pública | https://algatocin.sedelectronica.es/transparency/9175b609-54f9-43d4-8932-314c2642d78c/ | Ordenanzas no fiscales/fiscales + convocatoria pleno |
| Regularización SUN | https://algatocin.sedelectronica.es/transparency/77de26df-6bcd-4fbf-bf90-77fda4888737/ | **7 documentos** DAFO / regularización no urbanizable |
| Catálogo trámites | https://algatocin.sedelectronica.es/dossier | Sin listado histórico público |
| Consulta expedientes | https://algatocin.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| PGOU Diputación Málaga | https://www.malaga.es/delegacionfomento/planeamiento/ficha.asp?mun=29006&cod=736 | Documentos de avance PGOU |
| Punto Información Catastral | https://www.algatocin.es/10900/punto-informacion-catastral | Trámite presencial (c/ Fuente 2) |
| Ordenanza viviendas protegidas | https://www.algatocin.es/6873/ordenanza-del-registro-publico-municipal-de-demandantes-de-viviendas-protegidas-de-algatocin | Normativa urbanística |
| Tramita Algatocín | https://tramitaalgatocin.malaga.es | No responde desde CI |
| SITUA / VITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/ | Planeamiento regional; sin enlace por expediente ayto |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Alcaucín, Cártama, Coín.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** sin botón «Mostrar más» visible; ~6 filas actuales.

### Ejemplos encontrados (sep 2026)

| Expediente | Procedimiento | Descripción |
|------------|---------------|-------------|
| 140/2026 | Licencias de Ocupación | Bases licencia uso común especial caseta feria 2026 |
| 104/2026 | Procedimiento Genérico | Edicto información pública (empleo — no urbanismo) |

## Transparencia — urbanismo

- **Consulta pública previa:** carpeta vacía (sin documentos indexables).
- **Información pública:** subcarpetas ordenanzas no fiscales (4) y fiscales (1).
- **Regularización SUN:** ordenanza DAFO, tasa DAFO, modelos solicitud asimilado/fuera de ordenación (7 PDFs).

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor.
- Licencias de ocupación y actividad publicadas en tablón.
- Trámites informativos en sede `/dossier` y PIC catastral presencial.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Diputación Málaga / PRP Málaga: visor cartográfico provincial (`gis.prpmalaga.es`); sin ArcGIS REST accesible desde CI.
  - SITUA/VITUA (Junta de Andalucía): planeamiento digitalizado por municipio; PDFs escaneados sin geometría por expediente.
  - IDEMAP (https://www.idemap.es/): referenciado en web; sin WFS público enlazado a expedientes.
  - Datos geográficos web: solo lat/lon municipio (36°34' N, -5°16' W), sin visor urbanístico.
- **Estrategia:** documentos del tablón y transparencia son PDF sin georreferencia embebida ni enlace a visor por código de expediente.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS MapServer por expediente.
  - Consulta de expedientes requiere login.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Web municipal requiere User-Agent navegador (CloudFront WAF sin UA).
- Tablón con pocas filas; sin histórico extenso.
- Transparencia: subcarpetas ordenanzas requieren Wicket AJAX para navegar.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.algatocin:AlgatocinAyuntamientoAdapter`
- Fuentes: tablón sede + carpetas transparencia + PGOU Diputación + páginas informativas.
- IDs: `algatocin-lic-*` / `algatocin-proy-*` (sha256[:14]).
