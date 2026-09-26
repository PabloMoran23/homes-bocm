# Marines — investigación portal ayuntamiento

**Municipio:** Marines (Valencia / València, Comunitat Valenciana)  
**Slug:** `marines`  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)  
**INE municipio:** 46152

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.marines.es | **Intermitente** — Drupal portalesmunicipales; timeouts SSL frecuentes desde CI |
| Sede electrónica | https://marines.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://marines.sedelectronica.es/board/ | **Operativa** — tabla HTML (~1 fila urbanística actual) |
| Catálogo trámites | https://marines.sedelectronica.es/dossier/.0 | **Operativa** — 24 trámites urbanismo/licencias (sin histórico) |
| Consulta expedientes | https://marines.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| PAI UE Residencial 3a (PDF) | https://www.marines.es/sites/www.marines.es/files/PAI%20UE%20RESIDENCIAL%203a%20Marines.-.pdf | **Operativo** — documento planeamiento |
| Memoria urbanización UER-3A (PDF) | https://www.marines.es/sites/www.marines.es/files/DOC%201%20MEMORIA%20Y%20ANEJOS_f.pdf | **Intermitente** — timeout SSL ocasional |

## Cómo se listan expedientes

- **Tablón sede:** HTML Wicket con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. Enlaces a `/preview-document/{uuid}`.
- **Catálogo trámites:** listado estático en `/dossier/.0` con enlaces `/catalog/t/{uuid}` (procedimientos, no concesiones históricas).
- **Planeamiento publicado:** PDFs en `/sites/www.marines.es/files/` (PAI UER-3a, memoria de urbanización). No hay JSON/API pública.
- **Web Drupal:** sin `pagina-aviso` accesible (`/es/pagina-aviso` → 404); la home `/es` suele no responder en CI.

## Tablón sede (ago 2026)

| Expediente | Título | Fecha |
|------------|--------|-------|
| 464/2026 | Exposición pública aprobación inicial ordenanza cuota infraestructuras urbanísticas — urbanización El Romeral | 11/08/2026 |

## Planeamiento documentado (PDFs)

| Documento | Tipo | Fecha referencia |
|-----------|------|------------------|
| Plan Parcial UER-3a | plan parcial | Aprobación definitiva pleno 21/05/2020; DOGV 17/06/2021 |
| PAI UE Residencial 3a | programa de actuación integrada | DOGV 8837 (2021) |
| Memoria proyecto urbanización UER-3A | proyecto de urbanización | 2020 |

## Licencias de obra

- No hay dataset público de concesiones de licencia de obra mayor/menor.
- El catálogo de trámites incluye: solicitud licencia urbanística, declaración responsable urbanística, licencia de ocupación, primera ocupación, etc.
- El adapter incluye páginas informativas del tablón y trámites (patrón Benigànim/Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - ICV WFS `Planeamiento.Zonificacion` (terramapas.icv.gva.es/0702_Planeamiento): 0 features con `cod_ine_mun=46152` en barrido 0–15000.
  - ICV WFS `ms:InventarioSuSuz`: sin registros para INE 46152.
  - No hay visor urbanístico municipal ni ArcGIS/GeoJSON enlazado a expedientes.
- **Estrategia:** documentos y tablón son PDF/HTML sin georreferencia; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** sin polígonos por expediente; CQL_FILTER del WFS ICV no filtra correctamente en servidor.

## Limitaciones generales

- Web corporativa con timeouts SSL desde entornos CI (PDFs individuales más fiables que la home).
- Tablón con pocas filas urbanísticas; histórico no expuesto.
- Consulta de expedientes requiere login.
- Sin geometría enlazable.

## Adapter implementado

- `municipio.adapters.marines:MarinesAyuntamientoAdapter`
- Fuentes: documentos PDF estáticos + tablón sede + trámites dossier.
- IDs: `marines-lic-*` / `marines-proy-*` (sha256[:14]).
