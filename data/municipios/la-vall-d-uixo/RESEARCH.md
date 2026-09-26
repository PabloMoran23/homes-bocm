# La Vall d'Uixó — investigación portal ayuntamiento

**Slug:** `la-vall-d-uixo`  
**INE:** 12125 (Castellón / Comunitat Valenciana)  
**BOCM/DOGV:** 1 expediente en histórico regional

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial | https://www.lavallduixo.es | Drupal 9 (tema TOOOLS) |
| Planeamiento | https://www.lavallduixo.es/es/planeamiento-urbanistico | Índice PGOU, planes parciales, exposición pública |
| PGOU | https://www.lavallduixo.es/es/plan-general-de-ordenacion-urbana | Normativa general (sin PDFs directos en página) |
| Exposición pública | https://www.lavallduixo.es/es/exposicion-al-publico | Modificaciones puntuales (PDFs 2026) |
| Planes parciales | `/es/plan-parcial-sector-*`, `/es/plan-parcial-area-*` | Normas + planos PDF (2018) |
| PMUS | https://www.lavallduixo.es/es/pmus | Plan movilidad urbana sostenible |
| Sede electrónica | https://sede.lavallduixo.es | STA (no espublico) |
| Tablón | `.../doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON` | 66 anuncios (dataset JSON embebido) |
| Catálogo trámites | `.../doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO` | 279 trámites (~45 urbanismo/licencias) |

## Cómo se listan expedientes / proyectos

- **Drupal:** páginas estáticas por instrumento (PGOU, plan parcial, plan especial San José, PMUS) con enlaces a PDFs en `/sites/L01121264/files/`.
- **Exposición pública:** PDFs de modificaciones puntuales de planes parciales (sectores 9-A, 11).
- **Sede STA tablón:** variable `dataset_PTS2_TABLON` en HTML; campos `descriptionProc`, `pubDateIni`, `dboid`.
- **No hay** listado público de expedientes urbanísticos individuales ni visor municipal propio.

## Cómo se publican licencias

- **Tablón STA:** sin concesiones de licencia de obra recientes; mayoría anuncios fiscales/empleo.
- **Catálogo sede:** trámites informativos (licencia obra, DR, certificado urbanístico, etc.) sin histórico de concesiones.
- **No hay** dataset abierto de licencias concedidas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `Planeamiento.Zonificacion`: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Filtro `cod_ine_mun=12125` → 2 polígonos (Normas subsidiarias, exp. 19880195)
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** descarga WFS por paginación; matching título sector/plan parcial → polígono ICV cuando el nombre coincide; centroide WGS84.
- **Limitaciones:**
  - Solo normas subsidiarias PGOU en ICV; planes parciales sectoriales no georreferenciados en WFS.
  - Sin visor municipal ArcGIS ni WFS propio del ayuntamiento.
  - PDFs de planes sin coordenadas embebidas.
  - Sede requiere `insecure_ssl` (certificado intermitente desde CI).

## Limitaciones generales

- Portal Drupal sin API JSON; scrape HTML de semillas.
- Sede STA lenta (~40–70 s por petición tablón/catálogo).
- Licencias: solo trámites informativos del catálogo, no concesiones históricas.
- SSL sede: flag `sede_insecure_ssl: true` en manifest.
