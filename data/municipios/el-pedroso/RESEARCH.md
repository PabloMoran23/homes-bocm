# El Pedroso — investigación portal ayuntamiento

**Municipio:** El Pedroso (Sevilla, Andalucía)  
**Slug:** `el-pedroso`  
**INE:** 41073  
**CIF:** P4107300H  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://elpedroso.es | **Operativa** — WordPress (tema The7) |
| Punto información catastral | https://elpedroso.es/punto-de-informacion-catastral/ | Página informativa PIC |
| Sede electrónica | https://elpedroso.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://elpedroso.sedelectronica.es/board | **Operativa** — ~10 filas visibles |
| Portal transparencia | https://elpedroso.sedelectronica.es/transparency | Sección «7. URBANISMO…» (417 docs, AJAX) |
| Catálogo trámites | https://elpedroso.sedelectronica.es/dossier | Timeout frecuente en CI; sin listado histórico scrapeable |
| Consulta expedientes | https://elpedroso.sedelectronica.es/expedientes | Requiere identificación |
| Licencias Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4107300H | Portal provincial (CIF aviso legal) |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41073 | Planeamiento regional Junta de Andalucía |
| Turismo | https://turismo.elpedroso.es | Sin contenido urbanístico |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Tomares, Cártama, Ronda.
- **Listado:** tabla HTML con `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** `preview-document/{uuid}`.
- **UA:** requiere User-Agent tipo navegador (`Mozilla/5.0`); sin ello `/info.0` entra en bucle de redirección.
- **Contenido urbanístico visible (sep 2026):** ordenanza nº 36 prestación compensatoria suelo no urbanizable (nov 2025); ordenanza nº 11 piscina (ene 2025); resto edictos administrativos.

## Web WordPress

- Sin sección dedicada de urbanismo/planeamiento en el sitemap ni en páginas estáticas.
- Posts recientes: feria, subvenciones, formación — sin expedientes urbanísticos.
- Enlace a sede desde cabecera (`/info.0`).

## Licencias de obra

- No hay dataset municipal público de concesiones históricas.
- **Portal provincial:** Diputación de Sevilla LicytalPub con CIF `P4107300H`.
- Trámites vía sede `/dossier` y consulta `/expedientes` (autenticación).
- Tablón sede para edictos puntuales (sin licencias de obra en las 10 filas actuales).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal (ArcGIS/WFS) en web ni sede.
  - SITUA (Junta de Andalucía): cartografía de planeamiento por municipio (`cid=41073`), sin campo expediente del tablón ni WFS REST por expediente.
  - PIC catastral presencial; no API de parcelas enlazada a expedientes.
- **Estrategia:** documentos son PDF/listas HTML sin georreferencia; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Transparencia urbanismo (417 docs) requiere Wicket AJAX para subcarpetas.
  - Portal LicytalPub provincial no scrapeable de forma determinista.
  - INPRO tablón Diputación Sevilla (`ine=41073`) timeout en CI.
  - Sin `geom_geojson` en fuentes públicas del ayuntamiento.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Transparencia: árbol de 417 docs requiere sesión AJAX; solo índice raíz scrapeado.
- `/dossier` inestable (timeout >60s).
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.el_pedroso:ElPedrosoAyuntamientoAdapter`
- Fuentes: tablón sede + índice transparencia + SITUA + PIC web + páginas informativas licencias.
- IDs: `el-pedroso-lic-*` / `el-pedroso-proy-*` (sha256[:14]).
