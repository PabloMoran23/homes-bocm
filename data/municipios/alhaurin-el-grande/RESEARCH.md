# Alhaurín el Grande — investigación portal ayuntamiento

**Municipio:** Alhaurín el Grande (Málaga, Andalucía)  
**Slug:** `alhaurin-el-grande`  
**Boletín:** BOJA (`boja`, 20 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://alhaurinelgrande.es | **Operativa** — WordPress (Elementor) |
| Concejalía Urbanismo | https://alhaurinelgrande.es/concejalia-de-urbanismo/ | **Operativa** — PDFs PGOU, plan especial SURS-PE-1 |
| Sede electrónica | https://alhaurinelgrande.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://alhaurinelgrande.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Transparencia | https://alhaurinelgrande.sedelectronica.es/transparency | **Operativa** — sección «7. URBANISMO…» (17 docs, Wicket AJAX) |
| Catálogo trámites | https://alhaurinelgrande.sedelectronica.es/dossier.5 | Lenta; sin listado histórico público |
| App ciudadana iUrban | https://appnew.iurban.es/home | Portal SPA; sin API REST pública para expedientes |
| RPGUR (Junta Andalucía) | https://services8.arcgis.com/C7eTtVXWk1LWUjN8/ArcGIS/rest/services/RPGUR/FeatureServer | ArcGIS con capas PGOU; **requiere token** (error 499) |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Coín, Humanes, Algete.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente, p. ej. `23524/2025`)
  - `class_folderName` (procedimiento: Datos de la Vía Pública, Padrón Fiscal, …)
  - `class_boardCategory` (Anuncios, Empleo Público, …)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX con tokens de sesión; el adapter parsea la primera página (~10 filas).
- **Búsqueda:** formulario POST Wicket por descripción (no determinista sin sesión).

### Ejemplos urbanísticos encontrados (jul 2026)

| Expediente | Procedimiento | Descripción |
|------------|---------------|-------------|
| 23524/2025 | Datos de la Vía Pública | Audiencia expediente Urbanización Salmerón (publicación BOP) |

## WordPress — planeamiento / PGOU

La página de Concejalía de Urbanismo enlaza PDFs de planeamiento descargables:

| Documento | URL |
|-----------|-----|
| PGOU Planos clasificación urbanizaciones | `.../PGOU_Planos_I_Clasificacion_URBANIZACIONES.pdf` |
| PGOU Planos alturas casco | `.../PGOU_Planos_H_Alturas_CASCO.pdf` |
| Adaptación parcial LOU PGOU (memorias) | `.../MemoriasyAnexos_AdaptacionParcialLOUAdelPGOU.pdf` |
| Plan Especial SURS-PE-1 (memoria) | `.../MEMORIA-Division-Poligonal-SURS-PE-1.pdf` |
| Plan Especial SURS-PE-1 (planos) | `.../PLANOS-Division-Poligonal-SURS-PE.-1.pdf` |

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor.
- Las licencias publicadas aparecen en el tablón como edictos o anuncios de vía pública.
- Trámites informativos en sede `/dossier` (requiere certificado digital para solicitud).

## Proyectos / planeamiento

- **Tablón:** anuncios BOP, audiencias de urbanización, vía pública.
- **WordPress:** documentación PGOU y planes especiales en PDF.
- **Transparencia:** carpeta urbanismo con documentos adicionales (acceso vía Wicket AJAX, no scrapeado).
- Consulta de expedientes en sede requiere autenticación Cl@ve.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - App iUrban (`appnew.iurban.es`): portal ciudadano sin capas GIS descargables ni enlace a expediente.
  - RPGUR FeatureServer (Junta Andalucía): capas «Unidades de Actuación», «Instrumentos planeamiento desarrollo», etc.; API devuelve `Token Required` sin autenticación.
  - PDFs PGOU en WordPress: planos cartográficos sin georreferencia embebida ni campo expediente.
- **Estrategia:** no hay visor público con query por código de expediente. Los anuncios del tablón son PDF sin coordenadas.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - RPGUR requiere token OAuth/ArcGIS.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- Transparencia urbanismo requiere sesión Wicket para listar documentos.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.alhaurin_el_grande:AlhaurinElGrandeAyuntamientoAdapter`
- Fuentes: tablón sede + PDFs WordPress urbanismo + páginas informativas de trámites.
- IDs: `alhaurin-el-grande-lic-*` / `alhaurin-el-grande-proy-*` (sha256[:14]).
