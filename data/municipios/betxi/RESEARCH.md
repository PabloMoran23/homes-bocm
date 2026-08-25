# Betxí — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `betxi` |
| INE | 12021 |
| Provincia | Castellón/Castelló |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## Fuentes

### Web municipal (WordPress + Yoast SEO)

- Base: https://betxi.es
- Urbanisme / planeamiento: https://betxi.es/viure-a-betxi/urbanisme-2/
  - Normas subsidiarias (PDF), modificaciones puntuales NNSS (1–11), PMUS, PRI Molí de l'Horta
  - Enlaces a `/urbanisme/` (PDFs y documentos de tramitación)
- Trámites obras y urbanismo: https://betxi.es/lajuntament/administracio/tramits/tramits-obres-i-urbanisme/
  - Formularios licencia obra menor, DR, primera ocupación
- Plànol municipal (PDF/imagen, sin georreferencia): https://betxi.es/coneix-betxi/planol/

### Sede electrónica (espublico gestiona)

- Base: https://betxi.sedelectronica.es
- Tablón de anuncios: https://betxi.sedelectronica.es/board
  - HTML tabla Wicket; scrape estático (~8 anuncios recientes, mayoría presupuesto/personal)
- Trámites / catálogo: https://betxi.sedelectronica.es/dossier
- Portal transparencia: https://betxi.sedelectronica.es/transparency
  - Sección «Obres y urbanisme» (citizen-service)
- Servicio ciudadano urbanismo: https://betxi.sedelectronica.es/citizen-service/92426f7b-213a-4925-ace5-f4145545f963
- Consulta expedientes (login): https://betxi.sedelectronica.es/expedientes

### ICV / GVA — planeamiento

- WFS base: `https://terramapas.icv.gva.es/0702_Planeamiento`
- **InventarioSuSuz** (`ms:InventarioSuSuz`): 26 polígonos `cod_ine_mun=12021` (SU/SUZ, sectores Montserrat, Canyaret, Molí de l'Horta, etc.)
- **Zonificacion** (`ms:Planeamiento.Zonificacion`): 7 instrumentos únicos (NNSS, PP Palases, Molí d'en Llop, Camí Sant Francesc, mod. puntual N.4…)
- GeoJSON: `outputFormat=application/json; subtype=geojson`, `srsName=EPSG:4326`, `count=5000` (filtro cliente)
- Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias | Tablón sede (pocos edictos urbanos) + trámites sede + formularios web |
| Planeamiento | Página urbanisme web (PDFs) + capas ICV WFS + transparencia sede |
| Expedientes IP | No hay listado público; consulta sede con autenticación |

## Cómo se publican licencias

- Edictos en tablón sede (cuando existen)
- No hay dataset histórico de concesiones
- Trámites telemáticos vía sede (licencia obra, DR, primera ocupación)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV WFS `InventarioSuSuz` + `Planeamiento.Zonificacion` (`cod_ine_mun=12021`); visor cartografía GVA
- **Estrategia:** batch GeoJSON WFS (5000 features, filtro INE); geometría en respuesta para inventario; zonificación agrupada por expediente+denominación
- **Limitaciones:** tablón sin paginación AJAX en scrape estático; geometría ICV es ámbitos de planeamiento (SU/SUZ/PP), no parcela catastral; PDFs web sin georreferencia; consulta expedientes requiere login

## Limitaciones generales

- Tablón: solo anuncios recientes visibles sin AJAX
- Sin API REST pública de expedientes urbanísticos
- ICV batch 5000 features (~60s); CQL_FILTER no fiable en este servicio
- Transparencia urbanismo: enlace categoría sin UUID directo en índice
