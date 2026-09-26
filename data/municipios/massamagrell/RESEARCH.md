# Massamagrell — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `massamagrell` |
| INE (ICV) | 46164 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.massamagrell.es | Operativa — Drupal portalesmunicipales.es |
| Urbanismo | https://www.massamagrell.es/es/pagina/urbanismo | Operativa — oficina, Agenda Urbana PDF |
| Planos | https://www.massamagrell.es/es/content/planos | Operativa — planos callejeros |
| PMUS | https://www.massamagrell.es/va/pagina/plan-movilidad-urbana-sostenible-pmus | Operativa |
| Sede electrónica | https://massamagrell.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://massamagrell.sedelectronica.es/board | Operativa — tabla HTML preview-document |
| Transparencia | https://massamagrell.sedelectronica.es/transparency/ | Operativa — sección 7 urbanismo (60 docs) |
| Catálogo trámites | https://massamagrell.sedelectronica.es/dossier | Operativa |
| Consulta expedientes | https://massamagrell.sedelectronica.es/expedientes | Requiere autenticación |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / actividades | Tablón sede — filas HTML con expediente, procedimiento, PDF preview |
| Planeamiento | ICV WFS zonificación + InventarioSuSuz + transparencia sede |
| Urbanismo web | Página informativa + Agenda Urbana PDF |
| Trámites | Catálogo sede / dossier (sin histórico público de concesiones) |

### Tablón sede (agosto 2026)

- Sin licencias urbanísticas recientes visibles (~10 filas: fiestas, subvenciones, actividades, padrón)
- Procedimientos no urbanísticos predominan en el scrape estático

### Transparencia sede

- Sección **7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT** — 60 documentos
- Listado vía Wicket AJAX (no scrapeable estáticamente sin sesión)

## Cómo se publican licencias

- Edictos potenciales en tablón sede (`preview-document/...`)
- Sin dataset histórico de concesiones con coordenadas
- Trámites vía sede (requiere identificación para consulta expedientes)
- Adapter incluye páginas informativas de tablón y catálogo de trámites

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName zonificación: `Planeamiento.Zonificacion`
  - TypeName SUZ: `InventarioSuSuz`
  - Filtro municipio: `cod_ine_mun=46164` (8 instrumentos zonificación + 1 unidad SUZ)
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** escaneo paginado WFS GeoJSON; matching textual título↔`denominaci` (p. ej. «SECTOR 2» → «Homologación y plan parcial Sector 2 Industrial»)
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes parciales, no parcela catastral ni licencia individual
  - Sin visor cartográfico municipal propio identificado
  - Tablón paginado Wicket (~10 filas visibles sin AJAX)
  - Transparencia sede requiere AJAX para listado completo
  - Sede con certificado SSL caducado (`insecure_ssl: true`)

### Instrumentos ICV (cod_ine_mun=46164)

| Expediente | Denominación | Clasificación |
|------------|--------------|---------------|
| 19900578 | Plan general | SU |
| 19970407 | Homologación Sector 2 Cantallops | SUZ |
| 20010586 | Homologación y plan parcial Sector 2 Industrial | SUZ |
| 20010959 | Homologación y plan parcial Sector 5 la Magdalena | SUZ |
| 20020970 | Homologación y plan parcial Sector SUNP-1 | SUZ |
| — | UNIDAD DE ACTUACIÓN A5 (InventarioSuSuz) | SU |

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios recientes, sin urbanismo)
- Sin API REST de expedientes urbanísticos públicos
- Escaneo ICV WFS completo ~2 min (paginación × 500 features); cache en memoria por ejecución
- Provincia en `queue.yaml` incorrecta (`Massamagrell`); manifest usa `Valencia`

## Adapter implementado

- `municipio.adapters.massamagrell:MassamagrellAyuntamientoAdapter`
- Fuentes: tablón sede + ICV WFS zonificación/SUZ + páginas web informativas
