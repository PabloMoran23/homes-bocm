# Polop — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `polop` |
| INE | 03107 |
| Provincia | Alicante |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://polop.org | Operativa — WordPress (Genesis) |
| Urbanismo | https://polop.org/gestiones/urbanismo/ | Operativa — PGOU, planes parciales (Dropbox + JPG) |
| Instancias / ordenanzas | https://polop.org/gestiones/instancias-ordenanzas/ | Operativa — formularios PDF |
| Sede electrónica | https://polop.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://polop.sedelectronica.es/board// | Operativa — tabla HTML preview-document (~10 filas) |
| Catálogo trámites | https://polop.sedelectronica.es/dossier | Operativa |
| Consulta expedientes | https://polop.sedelectronica.es/expedientes | Requiere autenticación |
| Registro GVA planeamiento | https://politicaterritorial.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03107%20POLOP/ | Operativa — índice Apache |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Referencia zonificación |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / actividades | Tablón sede (edictos recientes) + instancias web |
| Planeamiento | ICV WFS + registro GVA + página urbanismo (enlaces Dropbox a MP/PGOU) |
| Trámites | Catálogo sede / dossier (sin histórico público de concesiones) |

### Tablón sede (octubre 2026)

~10 anuncios recientes; mayoría pleno/JGL/personal. Sin licencias urbanísticas en el scrape estático actual.

### Instrumentos ICV (cod_ine_mun=03107)

~53 polígonos de zonificación en WFS `Planeamiento.Zonificacion` (instrumentos PGOU, modificaciones puntuales, planes parciales).

## Cómo se publican licencias

- Edictos en tablón sede (`preview-document/...`) cuando hay convocatoria
- Formularios en «Instancias / Ordenanzas» (instancia general, ocupación vía pública)
- Sin dataset histórico de concesiones con coordenadas
- Consulta expedientes vía sede (requiere identificación)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=03107`
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** escaneo paginado WFS GeoJSON; instrumentos ICV como filas de proyectos con `geom_geojson`; matching textual título↔`denominaci` en tablón/PDFs
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes parciales, no parcela ni licencia individual
  - Sin visor municipal ArcGIS propio; documentación PGOU en Dropbox externo
  - Tablón paginado Wicket (~10 filas visibles sin AJAX)
  - Escaneo ICV WFS ~3 min por ejecución (cache en memoria del adapter)

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios recientes)
- Sin API REST pública de expedientes urbanísticos
- Provincia en `queue.yaml` incorrecta (`Polop`); manifest usa `Alicante`
- PDFs de planeamiento alojados en Dropbox (URLs estables en página urbanismo)

## Revisión por lotes (2026-10-21)

La cola se conserva tal como está en main hasta publicar con éxito. El export
excluye formularios, recursos reutilizables, referencias genéricas al portal y
licencias sin concesión acreditada. Las fechas observadas se conservan como
fecha_fuente y no se presumen fechas de concesión. Las fechas anuales no se
completan con un día inventado. La cobertura de licencias puede ser cero.
La publicación requiere datos reales, coordenadas y geografía válida.
