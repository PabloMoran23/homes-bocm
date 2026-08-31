# Onil — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `onil` |
| INE | 03091 |
| Provincia | Alicante |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.onil.es | Operativa — Joomla K2 (template boxme) |
| Sede electrónica (carpeta) | https://carpeta.onil.es/GDCarpetaCiudadano | Operativa — eAdmin Maggioli |
| Tablón de anuncios | https://carpeta.onil.es/GDCarpetaCiudadano/Tablon.do?action=verAnuncios | Operativa — tabla HTML (~206 filas) |
| Catálogo trámites | https://carpeta.onil.es/GDCarpetaCiudadano/Registrar.do?action=listadoEntradas | Operativa — sección Urbanismo (5 trámites) |
| Transparencia | https://transparencia.onil.es | Operativa — WordPress (Fusion) |
| Planeamiento | https://transparencia.onil.es/?page_id=185 | Operativa — PGOU, modificaciones puntuales (docs sede) |
| Urbanismo | https://transparencia.onil.es/?page_id=17 | Operativa — sección padre |
| Plano casco urbano | https://www.onil.es/images/planol/PlanoCascoUrbanoOnil.pdf | Operativo — PDF estático |
| Sede espublico | https://onil.sedelectronica.es | **Indeterminada** — página selector vacía |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Referencia ICV |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / obras | Tablón sede — filas HTML con título, periodo y PDF (`abrirOriginal` / `ValidarDocumento.do`) |
| Modelos solicitud | Tablón categoría `pa=ModelosySolicitudes` (formularios O-I_006 obra menor, etc.) |
| Planeamiento | Transparencia WP — acordeones PGOU/modificaciones con enlaces `abrir(token)` a sede |
| Trámites | Catálogo `Registrar.do` — modales informativos (obra mayor/menor, informe urbanístico) |

### Tablón sede (agosto 2026)

- **206 anuncios** visibles con POST vacío a `referenciaBusqueda`
- **~29 relacionados** con urbanismo/licencias/planeamiento (búsqueda por términos)
- Ejemplos: AGENDA URBANA 2030, modelos O-I_006 obra menor, O-I_028 obra mayor, PLAN ESTRATÉGICO ZONAL

## Cómo se publican licencias

- Modelos y formularios de licencia en tablón (`ModelosySolicitudes`) — trámites informativos
- Catálogo sede: obra mayor (95), obra menor/DR (96), informe urbanístico (59), espectáculos (85), animales peligrosos (50)
- Sin dataset histórico de concesiones con coordenadas ni listado de licencias otorgadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=03091` (15 instrumentos con polígonos)
  - Plano PDF casco urbano (sin georreferencia vectorial)
- **Estrategia:** escaneo paginado WFS GeoJSON; matching textual título↔`denominaci` (p. ej. «SECTOR EL PORTET» → «P.A.I. EN SECTOR 'EL PORTET'»)
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes parciales, no parcela ni licencia individual
  - Sin visor ArcGIS municipal público identificado
  - `transparencia.onil.es` requiere `insecure_ssl` (certificado)
  - `onil.sedelectronica.es` no operativa (sede indeterminada)
  - Tablón sin API JSON; scrape HTML tabla

### Instrumentos ICV (cod_ine_mun=03091, muestra)

| Expediente | Denominación |
|------------|--------------|
| 20040266 | P.A.I. EN SECTOR 'EL PORTET' |
| (otros) | Planes parciales, PGOU, modificaciones — 15 polígonos totales |

## Limitaciones generales

- Sede espublico (`onil.sedelectronica.es`) no usable
- Escaneo ICV WFS ~2 min (paginación 500 features × ~24 páginas); cache en memoria
- Provincia en `queue.yaml` incorrecta (`Onil`); manifest usa `Alicante`
- Web `/es/urbanismo` devuelve error 404 (página inexistente)

## Adapter implementado

- `municipio.adapters.onil:OnilAyuntamientoAdapter`
- IDs: `onil-lic-*` / `onil-proy-*` (sha256[:14])
