# Canillas de Albaida — investigación portal ayuntamiento

**Municipio:** Canillas de Albaida (Málaga, Andalucía)  
**Slug:** `canillas-de-albaida`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://canillasdealbaida.es | **Operativa** — WordPress Divi |
| Urbanismo | https://canillasdealbaida.es/urbanismo/ | **Operativa** — PDFs de planeamiento (PDSU, PMUS, PGOU, inventario caminos) |
| Participación ciudadana | https://canillasdealbaida.es/participacion-ciudadana/ | **Operativa** — consulta pública ordenanza urbanística |
| Impresos | https://canillasdealbaida.es/impresos/ | **Operativa** — autoliquidación de obras |
| Ordenanzas | https://canillasdealbaida.es/ordenanzas/ | **Operativa** |
| Sede electrónica | https://canillasdealbaida.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://canillasdealbaida.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://canillasdealbaida.sedelectronica.es/dossier | Trámites informativos |
| Consulta expedientes | https://canillasdealbaida.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional |
| Diputación Málaga | http://www.malaga.es/fomentoinfraestructuras/planeamiento/ficha.asp?mun=29033 | Ficha planeamiento (WAF CloudFront en CI) |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Coín, Alcaucín.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas estándar (`class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`).
- **Documentos:** enlace `preview-document/{uuid}`.
- **Contenido actual (sep 2026):** mayoría anuncios administrativos (cifra electores, subvenciones PAJ, edictos genéricos); sin licencias de obra recientes en primera página.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites informativos:
  - Autoliquidación de obras: https://canillasdealbaida.es/impresos/
  - Catálogo sede: https://canillasdealbaida.sedelectronica.es/dossier
  - Consulta expedientes (login): https://canillasdealbaida.sedelectronica.es/expedientes
- Las licencias concedidas se publican en el tablón como edictos cuando proceda.

## Proyectos / planeamiento

### Web municipal (urbanismo)

Documentación publicada en https://canillasdealbaida.es/urbanismo/:

| Documento | Tipo |
|-----------|------|
| Inventario Municipal de Caminos (sep 2025) | inventario caminos |
| PDSU — memoria, planos, fichas (2025) | Plan de Sostenibilidad Urbana |
| PMUS — memoria, resumen, anexos (2024) | Plan de Movilidad Urbana Sostenible |
| PGOU / EAE — planos y memorias (pdf/PLANOS/) | planeamiento general |
| Plan Municipal contra el Cambio Climático | PMCC |
| Documento de alcance EAE (feb 2025) | evaluación ambiental |

### Participación ciudadana

- Consulta pública previa a la Ordenanza Municipal Reguladora de los Instrumentos de Intervención en Materia Urbanística (adaptación a Ley 7/2021 LISTA).

### Tablón y sede

- Sin expedientes de planeamiento estructurados en sede; consulta requiere autenticación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): planeamiento regional; sin enlace por expediente del ayuntamiento.
  - PRP Málaga / Diputación: visores cartográficos provinciales; sin API REST enlazable a expedientes desde CI.
  - DERA WFS sistema urbano (`ideandalucia.es`): límites municipales y tejido urbano genérico, sin campo expediente.
  - PDFs de planeamiento en web municipal: planos raster sin georreferencia queryable.
- **Estrategia:** no hay visor municipal ni WFS con código de expediente; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin ArcGIS MapServer/FeatureServer municipal.
  - Tablón publica PDFs sin coordenadas.
  - Diputación Málaga bloqueada por CloudFront WAF desde CI.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- Consulta de expedientes requiere login.
- Web con muchos PDFs estáticos; el adapter extrae enlaces de urbanismo/participación/ordenanzas.

## Adapter implementado

- `municipio.adapters.canillas_de_albaida:CanillasDeAlbaidaAyuntamientoAdapter`
- Fuentes: tablón sede + PDFs web urbanismo + páginas informativas (sede, impresos, SITUA, Diputación).
