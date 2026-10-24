# Vila-real — investigación portal ayuntamiento

**Slug:** `vila-real`  
**INE:** 12135 (Castellón / Comunitat Valenciana)  
**BOCM/DOGV:** 1 expediente en histórico regional (`dogv`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial | https://www.vila-real.es/portal | CMS eAdmin (JSP), bilingüe ES/VA |
| Información urbanística | `p_85_contenedor5.jsp?codbusqueda=625` | Menú trámites urbanismo / certificados |
| Planes parciales | `s_ldoc_d11_v1.jsp?codbusqueda=1070` | Tabla HTML con PDFs (UHI-2, UHI-8, Europlataforma, etc.) |
| PGOU normas | https://www.vila-real.es/portal/RecursosWeb/DOCUMENTOS/1/0_43929_1.pdf | Texto consolidado agosto 2022 |
| Sede electrónica | https://seuelectronica.vila-real.es | STA TAO (T-Systems) |
| Tablón | `.../doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON` | ~270 anuncios (JSON embebido `dataset_PTS2_TABLON`) |
| Catálogo trámites | `.../doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO` | ~288 trámites (~44 urbanismo/licencias) |
| Visor municipal | http://app.vila-real.es | Timeout desde entorno cloud (sin respuesta) |

## Cómo se listan expedientes / proyectos

- **eAdmin:** listados documentales `s_ldoc_d11_v1.jsp` (nombre, fecha publicación web, enlace `s_fdoc_d4_v1.jsp?contenido=...`).
- **Menú urbanismo:** páginas `s_fdes_d4_v2.jsp` con `codbusqueda` 617–631 (certificados, consultas).
- **Sede STA tablón:** dataset JSON en HTML; campos `descriptionProc`, `pubDateIni`, `remitent`, `dboid`.
- **No hay** API REST ni visor de expedientes urbanísticos individuales enlazado a geometría.

## Cómo se publican licencias

- **Tablón STA:** pocas concesiones recientes de obra (mayoría empleo, juventud, fiscal).
- **Catálogo sede:** trámites informativos (licencia obra, DR obras, parcelación, urbanización) sin histórico de concesiones.
- **No hay** dataset abierto de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - ICV WFS `Planeamiento.Zonificacion` (`terramapas.icv.gva.es/0702_Planeamiento`): paginación 0–15000 sin features con `cod_ine_mun=12135`.
  - Visor GVA genérico: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion` (sin join a expediente municipal).
  - `http://app.vila-real.es` referenciado en menú urbanismo — no responde en CI.
- **Estrategia:** orquestador aplicará centroide municipal + jitter (`coord_source` geocode).
- **Limitaciones:** PDFs de planes sin georreferencia; tablón solo texto; sin WFS/ArcGIS municipal público accesible.

## Limitaciones generales

- Sede STA lenta (~25–35 s por petición tablón/catálogo).
- Portal JSP codificación mixta latin-1/utf-8 (adapter prueba ambas).
- Licencias: trámites informativos + escasos edictos en tablón, no registro histórico.
- `sede_insecure_ssl: true` por compatibilidad con certificado sede.
