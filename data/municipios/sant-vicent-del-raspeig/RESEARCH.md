# Sant Vicent del Raspeig — investigación portal ayuntamiento

**Municipio:** Sant Vicent del Raspeig / San Vicente del Raspeig (Alicante, Comunitat Valenciana)  
**INE:** `03132`  
**Sin boletín regional asociado en cola BOCM**

## URLs base y páginas semilla

| Rol | URL |
|-----|-----|
| Web corporativa (canónica) | https://raspeig.es |
| Dominio alternativo (cert SSL CN=raspeig.org) | https://www.santvicentdelraspeig.es |
| Sede electrónica | https://raspeig.sedipualba.es |
| Tablón de anuncios | https://raspeig.sedipualba.es/tablondeanuncios/ |
| Tablón RSS | https://raspeig.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo Urbanismo (área 1216) | https://raspeig.sedipualba.es/catalogoservicios.aspx?area=1216&ambito=1 |
| Información urbanística | https://raspeig.es/area/informacion-urbanistica/ |
| Planeamiento municipal | https://raspeig.es/planeamiento-urbanistico-municipal/ |
| Transparencia urbanismo | https://raspeig.es/transparencia-en-materias-de-urbanismo-obras-publicas-y-medioambiente/ |

## Tecnología

- **raspeig.es:** WordPress + Elementor (Yoast SEO, sitemaps `area-sitemap.xml`).
- **raspeig.sedipualba.es:** ASP.NET WebForms (Sedipualba). Tablón, catálogo de trámites, `ajax.aspx`.

## Proyectos / expedientes urbanísticos

1. **ICV InventarioSuSuz** — unidades de ejecución / sectores aprobados (p. ej. UE-3, UE-5, UE-6) con geometría WFS.
2. **Web WordPress** — secciones de planeamiento, transparencia y PDFs (`wp-content/uploads/…`) de modificaciones PGMO, plan especial Universidad de Alicante, Castellet, etc.
3. **Tablón sedipualba** — edictos y acuerdos; el RSS reciente mezcla padrón, mercados y RRHH; filtro por palabras clave urbanísticas.

**No hay** visor municipal de expedientes con enlace código↔polígono ni API JSON de planeamiento.

### Cómo se listan

- **WordPress:** páginas estáticas + enlaces PDF en `/wp-content/uploads/`.
- **Tablón:** RSS 2.0 (ISO-8859-1) + `anuncio.aspx?id=…`.
- **ICV:** WFS GML3 paginado (`STARTINDEX`), filtro cliente `cod_ine_mun=03132`.

## Licencias de obra

- **No hay** registro público de licencias concedidas (solo trámites y edictos).
- **Catálogo sede:** fichas URB11* (obra menor), URB13A (licencia ambiental), URB09A, documentos urbanísticos URB01*, etc.
- **Tablón:** edictos puntuales si se publican; ventana RSS mayoritariamente no urbanística.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` — `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
  - ~6 polígonos para INE 03132 (sectores UE/SUZ)
- **Estrategia:** ingestar sectores ICV con `geom_geojson`; enriquecer tablón/web por tokens sector (UE, SUZ, plan parcial).
- **Limitaciones:**
  - Tablón y PDFs WordPress sin geometría enlazada por expediente.
  - CQL server-side en ICV no fiable; filtro `cod_ine_mun` en cliente (paginación ~8k features).
  - `www.santvicentdelraspeig.es` falla verificación TLS (SAN); usar `raspeig.es`.

## Limitaciones generales

- Sin datos BOCM en `projects.json` para este municipio.
- Licencias: solo trámites informativos + edictos tablón filtrados.
