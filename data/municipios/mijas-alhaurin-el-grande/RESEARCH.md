# Mijas-Alhaurín El Grande — investigación portal ayuntamiento

**Entrada de cola compuesta:** alias BOCM que agrupa dos municipios de Málaga (Andalucía).  
**Slug:** `mijas-alhaurin-el-grande`  
**Boletín:** BOJA (`boja`, 1 entrada agregada en histórico)

| Municipio | Provincia | Web | Sede |
|-----------|-----------|-----|------|
| Mijas | Málaga | https://www.mijas.es/portal | https://mijas.sedelectronica.es |
| Alhaurín el Grande | Málaga | https://alhaurinelgrande.es | https://alhaurinelgrande.sedelectronica.es |

> Ambos municipios tienen adaptadores individuales (`mijas`, `alhaurin-el-grande`) ya integrados en el pipeline. Esta entrada reutiliza esos adaptadores vía composición.

## URLs base y páginas semilla

### Mijas

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.mijas.es/portal/ | **Operativa** — WordPress (qTranslate) |
| Sede electrónica | https://mijas.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://mijas.sedelectronica.es/board | **Operativa** — tabla HTML (~10/página) |
| Derecho a la información | `/portal/urbanismo/derecho-a-la-informacion/` | ZIP/PDF expedientes (~220 docs) |
| Planes parciales / especiales | `/portal/urbanismo/planes-parciales-de-ordenacion-planes-especiales-y-expedientes-de-adaptacion-al-pgou/` | Expedientes SUP/SUNP (~53 docs) |
| Licencias obra menor | `/portal/urbanismo/licencias-de-obra-menor-concedidas-por-decreto/` | PDFs históricos por decreto |

### Alhaurín el Grande

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://alhaurinelgrande.es | **Operativa** — WordPress (Elementor) |
| Concejalía Urbanismo | https://alhaurinelgrande.es/concejalia-de-urbanismo/ | PDFs PGOU, plan especial SURS-PE-1 |
| Sede electrónica | https://alhaurinelgrande.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://alhaurinelgrande.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |

## Cómo se listan expedientes

- **Mijas:** WordPress urbanismo (enlaces PDF/ZIP en páginas semilla) + tablón espublico (`preview-document/{uuid}`). Sin API REST.
- **Alhaurín el Grande:** tablón espublico + PDFs PGOU/planeamiento en WordPress. Transparencia sede con Wicket AJAX (no scrapeado).

## Licencias de obra

- No hay dataset público con coordenadas en ninguno de los dos municipios.
- Licencias aparecen como edictos en tablón o páginas informativas de trámites.
- Mijas publica PDFs históricos de licencias menores por decreto (sin filas individuales).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Mijas: sin visor urbanístico municipal; PRP Málaga (`gis.prpmalaga.es`) sin REST accesible desde CI; SITUA regional sin enlace expediente↔polígono.
  - Alhaurín el Grande: app iUrban (`appnew.iurban.es`) sin API GIS; RPGUR Junta de Andalucía requiere token ArcGIS.
- **Estrategia:** sin WFS/GeoJSON público enlazable a códigos de expediente; el orquestador aplica centroide municipal + jitter.
- **Limitaciones:** tablón y WordPress solo documentos PDF; sin polígonos por expediente.

## Adapter implementado

- `municipio.adapters.mijas_alhaurin_el_grande:MijasAlhaurinElGrandeAyuntamientoAdapter`
- Delega en `MijasAyuntamientoAdapter` y `AlhaurinElGrandeAyuntamientoAdapter`, fusionando salidas por `id`.
- IDs conservan prefijos originales (`mijas-*`, `alhaurin-el-grande-*`).

## Referencias

- Adaptadores individuales: `data/municipios/mijas/`, `data/municipios/alhaurin-el-grande/`
- Patrón multi-municipio: `municipio/adapters/benicarlo_vinaros_benijofar.py`
