# San Roque — investigación portal ayuntamiento

**Municipio:** San Roque (Cádiz, Andalucía)  
**Slug:** `san-roque`  
**BOJA:** 3 entradas en histórico regional

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web municipal | https://www.sanroque.es | Operativa con User-Agent navegador (403 FortiGate con UA genérico) |
| Documentación urbanismo | https://www.sanroque.es/documentos/urbanismo | Operativa — PDFs estudios de detalle, planes parciales, ordenanzas |
| Portal transparencia web | https://www.sanroque.es/documentacion | Enlaces a expedientes urbanísticos (`/portal-de-transparencia/…`) |
| Anuncios | https://www.sanroque.es/tipos-de-documentos/anuncios | Tablón documental web (mayoría no urbanismo) |
| Sede electrónica | https://sanroque.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://sanroque.sedelectronica.es/board/ | Operativa — tabla HTML Wicket (~10 filas visibles) |
| Transparencia sede | https://sanroque.sedelectronica.es/transparency | Operativa — enlace a tablón; sin carpeta urbanismo indexada |
| Trámites | https://sanroque.sedelectronica.es/dossier | Catálogo Wicket (lento; sin listado JSON) |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor PGOU regional (raster, sin API por expediente) |
| Gobierno abierto Dip. Cádiz | https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?entidadId=11032 | Catálogo transparencia provincial |

## Cómo se listan expedientes / proyectos

1. **Tablón sede (`/board/`):** tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Procedimiento mayoritario «Procedimiento Genérico». Ejemplos urbanismo: AMU «La Fábrica» (aprobación inicial estudio de ordenación), BOJA información pública modificación plan. Enlaces a `/preview-document/{uuid}`.
2. **Web `/documentos/urbanismo`:** listado Drupal con enlaces a portal de transparencia y PDFs en `/sites/default/files/files_documentacion/`. Incluye estudios de detalle (Torreguadiaro 019-TG, Sotogrande subsector 50, Cepsa petroquímico), modificaciones de planeamiento, ordenanza regularización edificaciones, cartografía suelo urbanizable (PDF).
3. **Portal transparencia web (`/portal-de-transparencia/…`):** páginas de expediente con título + PDF adjunto; sin API.

## Licencias de obra

- **No hay listado histórico** de licencias concedidas en portal público.
- El tablón sede puede publicar edictos de licencia puntuales (filtro regex).
- Trámites informativos en `/dossier` y consulta de expedientes autenticada (`/expedientes`).
- Adapter devuelve páginas informativas de referencia + edictos del tablón si aparecen.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUA Junta de Andalucía (`ws132.juntadeandalucia.es/situadifusion`) — planeamiento digitalizado raster (cod. municipio 11032), sin WFS/ArcGIS REST enlazable a código de expediente.
  - Web municipal — cartografía urbanística en PDF (`I.1_Suelo Urbano_Urbanizable_*.pdf`); módulo `geofield_gmap` presente pero sin capas urbanísticas consultables.
  - Diputación Cádiz gobierno abierto / IDE Cádiz — sin capas WFS urbanísticas para San Roque.
  - Sede espublico — documentos PDF sin coordenadas.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [36.2107, -5.3841]`).
- **Limitaciones:** planeamiento publicado como PDF; web bloqueada con UA genérico (FortiGate); tablón paginado (10 filas visibles).

## Limitaciones generales

- `www.sanroque.es` devuelve 403 con User-Agent de bot; adapter usa UA tipo navegador.
- Tablón sede: primera página visible (~10 filas); paginación Wicket AJAX no replicada.
- `/dossier` responde lento en CI; no scrapeado (solo enlace informativo licencias).
- Licencias históricas no publicadas en web abierta.

## Adapter

- `municipio.adapters.san_roque:SanRoqueAyuntamientoAdapter`
- IDs: `san-roque-lic-*` / `san-roque-proy-*` (sha256[:14]).
