# Orihuela — investigación portal ayuntamiento

**Municipio:** Orihuela (Alicante, Comunitat Valenciana)  
**Slug:** `orihuela`  
**INE:** 03099  
**Boletín:** sin boletín asociado en cola

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.orihuela.es | WordPress (TheGov) |
| Formularios urbanismo | https://www.orihuela.es/formularios/ | PDFs licencias obra, actividad, vía pública |
| Transparencia urbanismo | https://transparencia.orihuela.es/urbanismo-obras-y-medio-ambiente/ | Enlaces sede + BOP Diputación |
| Gobierno abierto | https://orihuela.governalia.es/ | WordPress transparencia |
| Sede espublico gestiona | https://orihuela.sedeelectronica.es | **Operativa** (certificado hostname mismatch → `insecure_ssl`) |
| Tablón anuncios | https://orihuela.sedeelectronica.es/board | HTML tabla + preview-document PDF |
| Inicio (extracto tablón) | https://orihuela.sedeelectronica.es/info.1 | Requiere sesión cookie Wicket |
| Catálogo trámites | http://orihuela.sedeelectronica.es/dossier | 183 trámites; usar **HTTP** (HTTPS bucle 302) |
| PGOU vigente | https://plangeneral.orihuela.es/pg90.html | Modificaciones puntuales PDF |
| Sede nueva (no usada) | https://sedeelectronica.orihuela.es | No resuelve en entorno agente |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Edictos / anuncios | Sede `/board` — tabla Wicket (expediente, procedimiento, categoría, fecha) |
| Planeamiento aprobado | ICV WFS `InventarioSuSuz` filtrado cliente `cod_ine_mun=03099` |
| Modificaciones PGOU | `plangeneral.orihuela.es/pg90/modificaciones/*.pdf` |
| Noticias urbanísticas | Búsqueda WP (`exposición pública`, `urbanismo`, ZBE…) |
| Transparencia sede | URLs `/transparency/{uuid}/` enlazadas desde portal transparencia |

El tablón vigente muestra ~10 filas por página (paginación Wicket AJAX; el adapter ingiere la primera página + inicio).

## Cómo se publican licencias

- Impresos descargables en `/formularios/` (obra menor/mayor, actividad, vía pública, andamios…)
- Catálogo sede (`/dossier`) con trámites de licencia urbanística y compatibilidad
- Sin dataset histórico de concesiones con coordenadas; tablón actual mayormente no urbanístico (vehículos, empleo)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa `InventarioSuSuz` — 137 instrumentos para `cod_ine_mun=03099` (PAU, HyPP, sectores costa, etc.)
  - Visor GVA genérico: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
- **Estrategia:** paginación WFS GML3 (`STARTINDEX` 200); polígonos en filas `origen=icv_wfs`; matching título↔sector para anuncios tablón
- **Limitaciones:**
  - Geometría es ámbito de planeamiento (SU/SUZ), no parcela ni licencia individual
  - Escaneo completo InventarioSuSuz ~2 min (8446 features CV, filtro cliente)
  - Certificado TLS sede no coincide con hostname (`insecure_ssl` obligatorio)
  - `/dossier` solo estable por HTTP; mezclar cookies board+dossier HTTPS provoca bucle redirect

## Limitaciones generales

- Tablón paginado sin API pública; solo primera página + extracto inicio
- `sedeelectronica.orihuela.es` inaccesible desde cloud agent
- Sin boletín BOCM/DOGV asociado en cola para este municipio

## Adapter implementado

- `municipio.adapters.orihuela:OrihuelaAyuntamientoAdapter`
- Fuentes: tablón sede + catálogo + PGOU PDFs + noticias WP + formularios + ICV WFS
- IDs: `orihuela-lic-*` / `orihuela-proy-*` (sha256[:14])
