# Alfarrasí — investigación portal ayuntamiento

**Municipio:** Alfarrasí (Valencia, Comunitat Valenciana)  
**Slug:** `alfarrasi`  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)  
**INE municipio:** 46027

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.alfarrasi.es | Operativa (intermitente) — Drupal 10 portalesmunicipales.es |
| Información urbanística | https://www.alfarrasi.es/es/transparencia/informacio-urbanistica | Operativa — PDFs PGOU, modificaciones y formularios licencias |
| Modificaciones PGOU | https://www.alfarrasi.es/es/transparencia/modificaciones-aprobadas-al-pgou | Operativa |
| Convenios urbanísticos | https://www.alfarrasi.es/es/transparencia/convenis-urbanistics | Operativa |
| Urbanismo (transparencia) | https://www.alfarrasi.es/es/transparencia/urbanismo | Operativa |
| Sede electrónica | https://alfarrasi.sede.dival.es | Operativa — Sedipualba (Dival) |
| Tablón de anuncios | https://alfarrasi.sede.dival.es/tablondeanuncios/ | Operativa — RSS disponible |
| Tablón RSS | https://alfarrasi.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Operativa |
| Catálogo trámites | https://alfarrasi.sede.dival.es/catalogoservicios.aspx | Operativa — solo trámites genéricos (registro, reclamaciones) |

### Documentos urbanísticos publicados (transparencia)

- Modificació Puntual nº 5 PGOU
- Modificació reparcelació forçosa sector sud est
- Urbanització sector sud residencial
- Llicència ambiental (recuperació plàstics)
- MODIFICACIÓ Nº 6 PGOU (modificacions 4 i 5, àrees d'actuació, pla d'ordenació, text refòs)

### Formularios licencias (PDF informativos)

- Obra menor / obra mayor
- Primera y segunda ocupación
- Declaración responsable obra menor

## Cómo se listan expedientes

- **Planeamiento:** PDFs enlazados en la sección transparencia → informació urbanística (Drupal field_collection).
- **Tablón sede:** RSS ASP.NET Sedipualba; en el scrape actual no hay edictos urbanísticos recientes (mayoría personal/ayudas).
- **No hay** visor urbanístico propio ni consulta pública de expedientes con geometría en el portal municipal.
- **ICV GVA:** inventario autonómico de planeamiento con polígonos por municipio.

## Licencias de obra

- Formularios PDF en transparencia (sin histórico de concesiones con coordenadas).
- Catálogo sede sin trámites de licencia urbanística en línea.
- Tablón electrónico para edictos; sin licencias publicadas en el momento del scrape.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capas: `Planeamiento.Zonificacion` (5 polígonos INE 46027) y `ms:InventarioSuSuz` (7 sectores SU/SUZ)
  - Campos: `cod_ine_mun`, `denominaci`, `pp`, `ue`, `expediente`, `f_aprob`
- **Estrategia:** paginación WFS (`startIndex` 0–13500, count 500) + match por tokens sector/PGOU en título del proyecto.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría en sede.
  - PDFs de modificaciones PGOU sin georreferencia embebida.
  - Tablón sin coordenadas; licencias solo formularios informativos.
  - Web municipal con latencia alta (timeouts ocasionales); adapter usa seeds estáticos de respaldo.

## Limitaciones generales

- Municipio pequeño: pocos expedientes publicados en tablón.
- Sede Dival sin trámites urbanísticos electrónicos.
- Provincia en `queue claim` aparece como `Alfarrasí`; manifest usa `Valencia`.
- Web en valenciano/castellano.

## Adapter implementado

- `municipio.adapters.alfarrasi:AlfarrasiAyuntamientoAdapter`
- Fuentes: ICV WFS + PDFs transparencia (static/crawl) + tablón RSS + formularios licencia informativos.
