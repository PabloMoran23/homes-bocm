# Petrer — investigación portal ayuntamiento

**Municipio:** Petrer (Alicante, Comunitat Valenciana)  
**Slug:** `petrer`  
**INE (ICV):** 03104  
**Boletín:** sin boletín asociado en cola BOCM

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|--------|
| Web oficial | https://petrer.es | WordPress (Hestia, Elementor) |
| Concejalía Urbanismo | https://petrer.es/concejalia-de-urbanismo/ | Trámites licencias (pestañas Elementor) |
| WP REST | https://petrer.es/wp-json/wp/v2/posts | Categoría `urbanismo` (id 188) |
| Sede electrónica | https://sede.petrer.es/ | STA T-Systems / TAO |
| Tablón | https://sede.petrer.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON&lang=ES | Formulario búsqueda; **sin** `dataset_*` embebido |
| Catálogo trámites | https://sede.petrer.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES | `dataset_CATSERV` (solo trámite genérico) |
| GeoPetrer | http://petrer.maps.arcgis.com/apps/webappviewer/index.html?id=ae0068931a864a2c83f916b9f7295fa5 | Visor ArcGIS Online municipal |

## Cómo se listan expedientes / planeamiento

| Tipo | Mecanismo |
|------|-----------|
| Información pública / noticias | WordPress — posts categoría Urbanismo + búsqueda «información pública», «modificación puntual», etc. |
| Documentación | PDFs en `wp-content/uploads/` enlazados desde posts |
| Instrumentos aprobados | ICV WFS `Planeamiento.Zonificacion` (`noms_mun=Petrer`, expediente 19960787 Plan general) |
| Tablón sede | Requiere búsqueda manual POST; no dataset JSON en HTML inicial |

Ejemplos recientes (2024–2026): Modificación Puntual nº 40–44 PGOU, Plan Parcial UZI-5 Luvi, IP Polideportivo San Jerónimo.

## Cómo se publican licencias

- Página urbanismo describe trámites: licencia obras (técnico / simplificada), compatibilidad urbanística, DR ocupación vivienda.
- **No** hay dataset histórico de concesiones con coordenadas ni listado en tablón scrapeable sin login/búsqueda.
- Sede: catálogo con trámite genérico telemático.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `Planeamiento.Zonificacion`, filtro `noms_mun=Petrer` (paginación `startIndex=2000`, ~2 polígonos Plan General con geometría GML).
  - GeoPetrer (ArcGIS Web AppViewer) — visor consulta; capas hosted en `petrer.maps.arcgis.com` (sin API pública documentada por expediente).
- **Estrategia:** descarga WFS GML3 → `geom_geojson`; enriquecimiento heurístico título↔«Plan general» en posts IP.
- **Limitaciones:**
  - Geometría ICV = delimitación PGOU/zonificación, no parcela de licencia.
  - Tablón STA sin filas embebidas; licencias sin coords públicas.
  - `InventarioSuSuz` no devolvió sectores Petrer en muestreo rápido.

## Limitaciones generales

- Tablón PTS2_TABLON devuelve error 404; PTS_TABLON operativo pero vacío sin POST.
- Muchas noticias urbanismo son subvenciones/obras ejecutadas (filtradas como ruido).
- Sin entradas BOCM en histórico parseado para este municipio.

## Adapter implementado

- `municipio.adapters.petrer:PetrerAyuntamientoAdapter`
- Fuentes: WP REST + trámites web urbanismo + ICV WFS Zonificacion
- IDs: `petrer-lic-*` / `petrer-proy-*` (sha256[:14])
