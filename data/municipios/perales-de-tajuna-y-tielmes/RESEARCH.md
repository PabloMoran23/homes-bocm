# Investigación portal — Perales de Tajuña y Tielmes

**Slug:** `perales-de-tajuna-y-tielmes`  
**Nota:** Entrada de cola generada por un anuncio BOCM que menciona dos municipios. **Perales de Tajuña** ya tiene adapter propio (`perales-de-tajuna`). Este onboarding agrega **Tielmes** y reutiliza la ingesta de Perales bajo el slug compuesto.

## URLs base y páginas semilla

### Perales de Tajuña (referencia / reutilizado)

| Recurso | URL | Notas |
|---------|-----|-------|
| Web Neosoft | https://www.ayto-peralestajuna.org | Planeamiento PDFs |
| Urbanismo | https://www.ayto-peralestajuna.org/paginas/urbanismo | NNSS, PONP Valdeperales, avance PGOU |
| Sede espublico | https://ayto-peralestajuna.sedelectronica.es | Tablón `/board` |
| Adapter existente | `municipio/adapters/perales_de_tajuna.py` | |

### Tielmes

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal | https://www.tielmes.es | ASP.NET / IIS |
| Licencias y urbanismo | https://www.tielmes.es/licencias-y-urbanismo | Trámites informativos (obra mayor/menor, calificación) |
| Transparencia — IP Cantarranas | https://www.tielmes.es/informacion-publica-y-consulta-de-calificacion-urbanistica-en-la-finca-molino-de-cantarranas | PDFs en `/Ficheros/Documentos/` |
| Sede electrónica | https://tielmes.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://tielmes.sedelectronica.es/board | Tabla HTML; enlaces PDF vía AJAX Wicket (sin `preview-document` directo en HTML) |
| Bandos | https://www.tielmes.es/bandos-y-anuncios | Sin urbanismo indexado scrapeable |

## Cómo se listan expedientes

- **Perales:** Tablón sede con `preview-document/{uuid}` + PDFs de planeamiento en web Neosoft.
- **Tielmes:** Sin visor de expedientes público. IP urbanística publicada como PDFs estáticos en transparencia (Molino de Cantarranas). Tablón sede lista filas (expediente, procedimiento, categoría) pero descarga de documento requiere sesión Wicket.

## Licencias

- **Perales:** Páginas informativas de trámites en sede + tablón cuando hay edictos.
- **Tielmes:** Página «Licencias y urbanismo» con requisitos; concesiones en tablón cuando se publican (actualmente mayoría empleo público / plenos).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Perales: WFS SITCM `sitcm:VPLA_V_AMBITO`, `DS_MUNICIPIO='PERALES DE TAJUÑA'` (5 ámbitos en WFS al scrapear)
  - Visor regional: https://idem.madrid.org/cartografia/sitcm/html/visor.htm
  - Tielmes: **0** features en `VPLA_V_AMBITO` para `DS_MUNICIPIO='TIELMES'`
- **Estrategia:** Enriquecer geometría en filas de Perales vía WFS (`returnGeometry`, GeoJSON EPSG:4326); Tielmes sin polígono enlazable a expediente
- **Limitaciones:** Tablón Tielmes sin URL PDF estable en HTML; sin visor municipal; IP Cantarranas solo PDF sin georreferencia

## Limitaciones

- Slug compuesto: `perales-de-tajuna` y eventual `tielmes` en cola pueden duplicar cobertura BOCM.
- Dominio `www.aytielmes.es` no resuelve DNS (usar `www.tielmes.es`).
- Sedes espublico: SSL verificado en Perales con `insecure_ssl` heredado del adapter base.
