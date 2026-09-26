# Beas de Segura — investigación portal ayuntamiento

**Municipio:** Beas de Segura (Jaén, Andalucía)  
**Slug:** `beas-de-segura`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)  
**INE:** 23015

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.beasdesegura.es | **Operativa** — WordPress Colibri (Diputación Jaén / webaytos.dipujaen.es) |
| Urbanismo (web) | https://www.beasdesegura.es/ayuntamiento/urbanismo/ | **Vacía** — «No hay publicaciones de Urbanismo» |
| Áreas municipales | https://www.beasdesegura.es/ayuntamiento/areas/ | Enlaces a reglamentos/ordenanzas generales y urbanismo (sin PDFs indexados) |
| Sede electrónica | https://beasdesegura.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://beasdesegura.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://beasdesegura.sedelectronica.es/dossier | Timeout frecuente en CI |
| Consulta expedientes | https://beasdesegura.sedelectronica.es/expedientes | Requiere autenticación |
| Portal transparencia sede | https://beasdesegura.sedelectronica.es/transparency/ | Sin carpetas de planeamiento estructuradas |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional digitalizado (Jaén) |
| Turismo | https://www.turismobeasdesegura.es/ | Sin datos urbanísticos |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Baeza, Coín.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}` (PDF en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Expediente | Procedimiento | Descripción |
|-------|------------|---------------|-------------|
| 10/08/2026 | 430/2026 | Certificados o Informes | Anuncio información pública obras paso sobre camino en cauce Los Cortijillos — parcela 9030 polígono 50 |
| 06/08/2026 | 790/2026 | Declaraciones Responsables o Comunicaciones Urbanísticas | Vallado perimetral de finca en zona de policía de Arroyo Fuente Pinilla (polígono 52, parcela 302) |

## Licencias de obra

- No hay dataset público de concesiones de obra con coordenadas.
- Trámites vía sede electrónica (`/dossier`, `/tramites-disponibles`); sin listado histórico público.
- Las comunicaciones urbanísticas y declaraciones responsables publicadas aparecen en el tablón.
- Sección web de urbanismo sin formularios ni histórico de licencias.

## Proyectos / planeamiento

| Origen | Contenido |
|--------|-----------|
| Tablón sede | Información pública de obras, comunicaciones urbanísticas |
| SITUA | Planeamiento general aprobado (visor regional Junta de Andalucía) |
| Web municipal | Sección urbanismo vacía; áreas con enlace normativo genérico |
| Transparencia sede | Sin registro IOU estructurado como en Baeza |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): planeamiento escaneado por municipio (INE 23015); sin API REST/WFS enlazable por código de expediente del tablón.
  - Web municipal: sin visor urbanístico ArcGIS ni GeoJSON en datos abiertos.
  - Tablón: anuncios en PDF sin georreferencia embebida.
- **Estrategia:** no hay visor municipal ni capa WFS con campo expediente. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - SITUA requiere selección interactiva de municipio; sin query programática por expediente.
  - `/dossier` inestable (timeout) en entorno CI.
  - Sin geometría por fila de expediente.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sección urbanismo web vacía.
- Consulta de expedientes requiere login.
- Sin portal transparencia municipal dedicado (solo sede espublico).

## Adapter implementado

- `municipio.adapters.beas_de_segura:BeasDeSeguraAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas (sede y web) + referencia SITUA.
- IDs: `beas-de-segura-lic-*` / `beas-de-segura-proy-*` (sha256[:14]).
