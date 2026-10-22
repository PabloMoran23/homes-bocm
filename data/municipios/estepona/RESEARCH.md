# Estepona — investigación portal ayuntamiento

**Municipio:** Estepona (Málaga, Andalucía)  
**Slug:** `estepona`  
**INE:** 29051  
**Boletín:** sin boletín regional asociado en cola BOCM

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.estepona.es | Noticias y servicios; poca documentación urbanística |
| Ayuntamiento (noticias) | https://ayuntamiento.estepona.es | WordPress; delegación Urbanismo con descargas puntuales |
| Sede electrónica | https://estepona.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://estepona.sedelectronica.es/board | **Operativa** — tabla HTML Wicket (~10 filas/página) |
| Portal transparencia | https://transparencia.estepona.es/visual/informacion-urbanistica-y-territorial/ | WordPress + enlaces a sede transparencia |
| Transparencia sede — PGOU | https://estepona.sedelectronica.es/transparency/91db2349-8f7e-47b7-a429-81192079f13a/ | Indicadores con carpetas (13 PGOU, 37 planos) |
| Transparencia sede — planeamiento | https://estepona.sedelectronica.es/transparency/5fdc2c2e-76a5-4c12-8274-2f5dcb7550bc/ | Convenios, planes parciales, calificación ambiental |
| Catálogo trámites | https://estepona.sedelectronica.es/dossier | Trámites sin histórico de concesiones |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=29051 | Planeamiento digitalizado CCAA |
| Visor SITES | https://sites.estepona.es/VisorWebGIS/#/SITEstepona | Angular SPA — calificación, usos, catastro |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Mijas, Ronda, Coín.
- **Listado:** columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** `preview-document/{uuid}`.
- **Procedimientos urbanísticos:** «Planeamiento de Desarrollo», licencias, calificación ambiental (cuando aparecen en portada).
- **Paginación:** «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página.

### Ejemplos urbanísticos (referencia pública)

| Expediente | Procedimiento | Descripción |
|------------|---------------|-------------|
| 37453/2025 | Planeamiento de Desarrollo | Vivienda unifamiliar Finca Loma del Monte |
| 39752/2023 | Planeamiento de Desarrollo | Vivienda unifamiliar parcela 49 polígono 26 Cortijo Reinoso |

## Transparencia — planeamiento y licencias

- Sección WP enlaza seis bloques en sede transparencia (PGOU, planeamiento/gestión/licencias, obras públicas, etc.).
- Carpetas `gIconLink exp` muestran indicadores de cumplimiento con conteo de documentos (p. ej. 13 documentos PGOU, 37 planos).
- Los PDFs individuales requieren navegación Wicket/AJAX; el adapter indexa títulos de carpeta + URL de sección.

## Licencias de obra

- No hay dataset histórico público de concesiones (como en Mijas/Ronda).
- Edictos y licencias en tablón cuando el procedimiento lo publica.
- Declaraciones responsables y licencias vía catálogo `/dossier` (solo trámites, sin listado).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **SITES** (`sites.estepona.es/VisorWebGIS`): visor municipal integrado con sede; consulta calificación, usos y parcela/catastro en cliente Angular.
  - **Catastro:** enlace a sedecatastro desde el visor (consulta por ref. catastral en UI).
  - **SITUA:** documentos de planeamiento escaneados (sin geometría vectorial por expediente).
- **Estrategia:** el visor no expone MapServer/FeatureServer REST en URLs estáticas accesibles desde CI; no hay join expediente tablón → `objectId` GIS. Geometría de filas vía orquestador (centroide municipio + jitter) salvo futura API ref. catastral.
- **Limitaciones:**
  - SPA sin endpoint ArcGIS/WFS documentado en assets públicos.
  - Tablón sin referencia catastral sistemática en descripciones.
  - Expedientes en sede requieren autenticación.

## Limitaciones generales

- Tablón paginado (primera página en adapter).
- Transparencia sede: descarga profunda de PDFs vía Wicket.
- Sin boletín BOCM regional en histórico del proyecto para este municipio.

## Adapter implementado

- `municipio.adapters.estepona:EsteponaAyuntamientoAdapter`
- Fuentes: tablón sede + carpetas transparencia sede + semillas SITUA/SITES/transparencia WP.
- IDs: `estepona-lic-*` / `estepona-proy-*` (sha256[:14]).
