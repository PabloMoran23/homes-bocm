# Láchar — investigación portal ayuntamiento

**Municipio:** Láchar (Granada, Andalucía)  
**Slug:** `lachar`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://lachar.es | **Operativa** — plataforma Saga Suite (Diputación Granada) |
| Sede electrónica | https://lachar.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://lachar.sedelectronica.es/board | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://lachar.sedelectronica.es/dossier | Trámites DIPGR (licencias, consulta urbanística) |
| Consulta expedientes | https://lachar.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Portal transparencia (sede) | https://lachar.sedelectronica.es/transparency | Categoría «Urbanismo, obras públicas y medio ambiente» (0 documentos) |
| Plan ordenación urbana | https://lachar.es/ayuntamiento/plan-de-ordenacion-urbana/ | POU/PGOU informativo + enlace a sede |
| SITUADIFUSION | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento digitalizado regional |
| BOJA PGOU normas | https://www.juntadeandalucia.es/boja/2020/208/69 | Publicación normas urbanísticas 2020 |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), plantilla Diputación Granada (trámites DIPGR).
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos / medio ambiente (sep 2026)

| Fecha | Expediente | Descripción |
|-------|------------|-------------|
| 23/09/2026 | 712/2026 | INICIO ACTUACIONES LIMPIEZA DE VERTIDO PP1R (Procedimiento Genérico) |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites destacados en sede (plantillas DIPGR):
  - DIPGR-Solicitud de Licencia de Edificación, Obras e Instalaciones
  - DIPGR-Solicitud de Licencia de Parcelación/Segregación/División Horizontal
  - DIPGR-Declaración Responsable (con/sin documentación técnica)
  - DIPGR-Consulta Urbanística
- Las licencias concedidas se publican en el tablón cuando procede (edictos).

## Proyectos / planeamiento

- **PGOU** aprobado definitivamente 26/03/2003; normas publicadas en BOJA 16/10/2020.
- **Innovación nº 1** revisión normas subsidiarias Peñuelas (recalificación industrial→residencial), publicada BOJA 2022.
- **Web municipal:** sección plan de ordenación urbana con enlace a «Acceso a Urbanismo» en sede.
- **Transparencia sede:** categoría urbanismo sin documentos indexados (0).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUADIFUSION / VITUA (Junta de Andalucía): planeamiento escaneado; sin API REST por código de expediente del ayuntamiento.
  - No hay visor urbanístico municipal (ArcGIS/GeoVistas) enlazado desde la web de Láchar.
  - Tablón: PDFs sin georreferencia embebida.
- **Estrategia:** el orquestador usará centroide municipio + jitter (`centroid` en manifest).
- **Limitaciones:** consulta de expedientes requiere login; transparencia urbanismo vacía; sin WFS por expediente.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- `/dossier` puede ser lento en CI.

## Adapter implementado

- `municipio.adapters.lachar:LacharAyuntamientoAdapter`
- Fuentes: tablón sede + páginas estáticas PGOU/BOJA/SITUA + trámites informativos DIPGR.
