# Castellar (Castellar de la Frontera, Cádiz)

Municipio andaluz en la comarca del Campo de Gibraltar. Población ~3.020 hab. (INE 2023).
Boletín: BOJA (`boletin_source_id: boja`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://castellardelafrontera.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://castellardelafrontera.sedelectronica.es/board/ | Anuncios BOP/BOPA con preview-document UUID |
| Web municipal | https://www.castellardelafrontera.es/ | Joomla + YooTheme; ordenanzas vía Phoca Download |
| Ordenanzas | https://www.castellardelafrontera.es/ayuntamiento/ordenanzas | Reglamentos (no histórico de licencias) |
| Planeamiento Dip. Cádiz | https://www.dipucadiz.es/.../castellar/ | PGOU 2003, PBOM y Plan Especial Castillo en tramitación |
| PBOM (cartografía) | https://www.dipucadiz.es/.../castellar/pbom/ | Hojas cartográficas PDF (1075-xx-xx) |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf?municipiosSeleccionados=11013 | PGOU vigente (código INE 11013) |

## Expedientes / proyectos

- **Tablón sede (`/board/`)**: filas HTML con clases `class_name`, `class_folderCode`, `class_folderName`, etc. Enlaces a `/preview-document/{uuid}`. Procedimientos urbanísticos detectados: «Licencias Urbanísticas» (p. ej. exp. 241/2022, anuncio IP Junta AT-15003-22).
- **Diputación Cádiz**: documentación de planeamiento (PGOU 2003 adaptado LOUA; PBOM en actos preparatorios; Plan Especial Castillo). Cartografía en PDF por hojas MTN.
- **SITUA**: visor JSF de planeamiento general aprobado; no expone expedientes individuales del ayuntamiento.
- **Transparencia sede**: sección «Urbanismo, Obras Públicas y Medio Ambiente» sin documentos urbanísticos indexables (solo empleo público en muestra).
- **BOJA**: modificaciones PGOU (exp. 841/2021 sector Castellar-Golf), sectorización SUNS-1 Castellar Norte (2024) — ya en pipeline BOCM, no re-parseados.

## Licencias de obra

- No hay registro público de licencias concedidas (tipo Licytal).
- Tablón publica anuncios de información pública de licencias (Junta/delegación) y trámites genéricos.
- Trámites de licencia/comunicación previa en sede (`/dossier`, categoría Urbanismo y Vivienda) requieren certificado digital; `/dossier` devuelve bucle 302 sin sesión.
- Ordenanzas web: modelos normativos, no concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SITUA (Junta): planeamiento general PGOU 2003 por municipio INE 11013 — visor JSF, sin WFS/ArcGIS query por código de expediente.
  - Diputación: cartografía PBOM en PDF (hojas 1075-08-05 … 1075-13-12) — sin georreferencia vectorial descargable.
  - No visor urbanístico municipal (ArcGIS/WFS) enlazado a expedientes del tablón.
- **Estrategia:** metadatos desde tablón + documentación Diputación/SITUA; coordenadas vía centroide municipal + jitter en orquestador (`geocode`).
- **Limitaciones:** preview-document son PDFs sin enlace GIS; SITUA no permite lookup por exp. ayuntamiento; dossier urbanismo requiere autenticación.

## Limitaciones generales

- SSL sede: certificado válido pero algunos paths (`/info`, `/dossier`) redirigen en bucle; adapter usa `/board/` directamente.
- Tablón paginado (8 filas visibles; enlace «Más publicaciones»).
- Web Joomla `/es/*` obsoleta (404); rutas actuales sin prefijo `/es/`.
- Sin API JSON pública; scrape HTML determinista.
