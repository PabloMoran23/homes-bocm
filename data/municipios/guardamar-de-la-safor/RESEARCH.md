# Guardamar de la Safor — investigación portal ayuntamiento

**Municipio:** Guardamar de la Safor (Valencia / València, Comunitat Valenciana)  
**Slug:** `guardamar-de-la-safor`  
**INE:** `46140` (no confundir con `46138` = Guadasséquies)  
**CIF:** P4614200F  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://guardamardelasafor.org | Operativa — WordPress (Accesia Soluciones SL) |
| Web ES | https://guardamardelasafor.org/es/ | Home con enlace a sede y transparencia |
| Urbanismo | https://guardamardelasafor.org/es/serveis-municipals/urbanisme/ | Operativa — PDFs PGOU/planes parciales |
| Plànol municipi | https://guardamardelasafor.org/es/poble/planol-del-municipi/ | Operativa — página sin mapa descargable (solo enlace) |
| Normativa municipal | https://guardamardelasafor.org/es/ajuntament/normativa-municipal/ | Ordenanzas fiscales (ICIO) y no fiscales |
| Sede electrónica | https://guardamardelasafor.sedelectronica.es | Operativa — espublico gestiona / eHome (Wicket) |
| Tablón de anuncios | https://guardamardelasafor.sedelectronica.es/board | Operativa — **vacío** (sep 2026) |
| Catálogo trámites | https://guardamardelasafor.sedelectronica.es/dossier | Lento / redirecciones; trámites sin histórico |
| Consulta expedientes | https://guardamardelasafor.sedelectronica.es/expedientes | Requiere autenticación |
| Portal transparencia sede | https://guardamardelasafor.sedelectronica.es/transparency | Operativa — carpetas LGT (7 = urbanismo, 6 docs) |
| Registro entidades GVA | http://www.entidadeslocales.gva.es/index.php?id=46140&option=com_reglocal_entloc&task=muestraEntidad&tipo=1 | Ficha oficial INE/CIF |
| Reg. planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46140%20GUARDAMAR%20DE%20LA%20SAFOR/ | Índice instrumentos (PG 2001/1225, PGMOD nº7) |
| Visor cartografía GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Referencia ICV |
| Datos abiertos GVA | https://dadesobertes.gva.es/es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica | WFS/WMS/GPKG zonificación CV |

## Cómo se listan expedientes / proyectos

| Tipo | Mecanismo | Formato |
|------|-----------|---------|
| Planeamiento / PGOU | Web WordPress `/urbanisme/` | HTML estático + enlaces PDF (`wp-content/uploads/...`) |
| Instrumentos oficiales | Registro planeamiento GVA (`mediambient.gva.es`) | Índice de carpetas + PDFs |
| Zonificación | ICV WFS `Planeamiento.Zonificacion` | GeoJSON/GML (filtro cliente `cod_ine_mun=46140`) |
| Anuncios / IP | Tablón sede `/board` | HTML tabla Wicket + `preview-document/{uuid}` |
| Transparencia | Sede `/transparency` carpeta 7 | Wicket AJAX (carpetas expandibles, 6 documentos) |
| Contratación | contratosmenores.es / transparencia | PUAM exp. `10/2024`, obras varias |

**No hay** listado JSON/API de expedientes urbanísticos, visor municipal propio ni Drupal `pagina-aviso` (patrón Benigànim).

### PDFs urbanismo web (sep 2026)

| Etiqueta | URL |
|----------|-----|
| VER NORMATIVA (NNSS/PGOU) | https://guardamardelasafor.org/wp-content/uploads/2024/09/ayuntamiento-479592587.pdf |
| SOLO INDUSTRIAL (plan parcial sector industrial) | https://guardamardelasafor.org/wp-content/uploads/2024/09/ayuntamiento-864083815.pdf |
| CASCO URBANO | https://guardamardelasafor.org/wp-content/uploads/2024/09/ayuntamiento-1104848687.pdf |
| ENSANCHE CASCO URBANO | https://guardamardelasafor.org/wp-content/uploads/2024/09/ayuntamiento-447295644_compressed.pdf |
| RESIDENCIAL BAJA DENSIDAD PUEBLO | https://guardamardelasafor.org/wp-content/uploads/2024/09/ayuntamiento-2024645708.pdf |
| SECTOR BAJA DENSIDAD PLAYA | https://guardamardelasafor.org/wp-content/uploads/2024/09/ayuntamiento-1400070421_compressed.pdf |
| Sector residencial PLAYA | https://guardamardelasafor.org/wp-content/uploads/2024/09/ayuntamiento-415328093_compressed.pdf |
| SUELO NO URBANIZABLE PROTECCIÓN AGRÍCOLA | https://guardamardelasafor.org/wp-content/uploads/2024/09/ayuntamiento-1233469931.pdf |

## Cómo se publican licencias

- **Tablón sede** (`/board`): mecanismo estándar espublico para edictos de licencias, actividades e información pública. **Actualmente sin filas** («No se han encontrado elementos»).
- **Trámites destacados sede** (informativos, sin histórico de concesiones):
  - Solicitud de Licencia Municipal de Primera Ocupación
  - Solicitud de Licencia Municipal de Segunda Ocupación
  - Declaración Responsable para la ejecución de obras de reforma de edificios y construcciones
- **Sección catálogo:** `02. Urbanismo y vía pública` (acceso vía `/dossier`, sin listado público de concesiones).
- **Sin dataset** histórico de licencias concedidas con dirección/coordenadas.
- **Ordenanza ICIO** publicada en normativa municipal y PDFs de boletín oficial en web.

## Geometría / visor

- **geometry_status:** `partial`
- **Motivo:** ICV WFS aporta polígonos de zonificación del Plan General (exp. `20011225`), pero no geometría de licencias ni expedientes del tablón. Sin visor urbanístico municipal.

### Fuentes GIS

| Servicio | URL / capa | Notas |
|----------|------------|-------|
| ICV WFS | `https://terramapas.icv.gva.es/0702_Planeamiento/wfs` | `typeName=Planeamiento.Zonificacion` |
| ICV WMS | `https://terramapas.icv.gva.es/0702_Planeamiento/wms` | Capa `Planeamiento.Zonificacion` |
| GeoJSON | `outputFormat=application/json; subtype=geojson`, `srsName=EPSG:4326` | Por `featureId=Planeamiento.Zonificacion.{id}` |
| GML3 | `outputFormat=GML3` | Paginación `STARTINDEX` + `count=500` |
| Visor GVA | `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion` | Visualización regional |
| Reg. planeamiento | `https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46140%20GUARDAMAR%20DE%20LA%20SAFOR/` | PDFs instrumentos |

### ICV — polígonos `cod_ine_mun=46140` (5 features, sep 2026)

| featureId | expediente | clas_suelo | zon_suelo | descripción |
|-----------|------------|------------|-----------|-------------|
| 945 | 20011225 | SUZ | ZND-IN | Zona nuevo desarrollo industrial |
| 4170 | 20011225 | SUZ | ZND-RE | Zona nuevo desarrollo residencial |
| 4136 | 20011225 | SUZ | ZND-RE | Zona nuevo desarrollo residencial |
| 4250 | 20011225 | SUZ | ZND-RE | Zona nuevo desarrollo residencial |
| 4252 | 20011225 | SUZ | ZND-RE | Zona nuevo desarrollo residencial |

- **CQL_FILTER** en servidor no es fiable (`cod_ine_mun='46140'` devuelve mezcla); filtrar en cliente o usar `featureId` puntual.
- Escaneo paginado completo ~60–90 s (offsets cada 500 hasta ~15000).
- `url_abs` en features apunta al registro GVA del municipio.

### Estrategia adapter

1. **Proyectos:** semillas PDF web urbanismo + carpeta transparencia sede + instrumentos GVA + ICV WFS.
2. **Licencias:** tablón `/board` (regex urbanismo/licencias) + trámites informativos sede.
3. **Geometría:** fetch ICV por `featureId` conocidos; matching textual título↔`zon_suelo` (p. ej. «industrial», «playa», «casco»).
4. **Sin geometría:** centroide municipio ~`[38.961, -0.155]` + jitter.

## Endpoints scrapeables

```
# Tablón (HTML Wicket)
https://guardamardelasafor.sedelectronica.es/board

# Documentos tablón/transparencia
https://guardamardelasafor.sedelectronica.es/preview-document/{uuid}

# Urbanismo web (PDFs)
https://guardamardelasafor.org/es/serveis-municipals/urbanisme/

# ICV WFS — feature puntual (GeoJSON WGS84)
https://terramapas.icv.gva.es/0702_Planeamiento/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=Planeamiento.Zonificacion&outputFormat=application/json;%20subtype=geojson&featureId=Planeamiento.Zonificacion.945&srsName=EPSG:4326

# ICV WFS — paginación (GML3)
https://terramapas.icv.gva.es/0702_Planeamiento/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=Planeamiento.Zonificacion&outputFormat=GML3&count=500&STARTINDEX=0

# Registro planeamiento GVA
https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46140%20GUARDAMAR%20DE%20LA%20SAFOR/
```

## Patrones similares en el repo

| Municipio | Adapter | Patrón aplicable |
|-----------|---------|------------------|
| Alfafar | `municipio.adapters.alfafar` | espublico `/board` + ICV WFS `cod_ine_mun` + transparencia |
| Enguera | `municipio.adapters.enguera` | espublico + transparencia urbanismo UUID + ICV `featureId` |
| Benigànim | `municipio.adapters.beniganim` | CV WordPress avisos + sede espublico (tablón vacío) |
| Canals | `municipio.adapters.canals` | ICV WFS paginado + matching keywords |
| Dénia | `municipio.adapters.denia` | ICV WFS + tablón STA (Guardamar no tiene STA) |

**Patrón más cercano:** Alfafar / Enguera (misma plataforma sede espublico + ICV GVA).

## Limitaciones

- Tablón sede vacío en sep 2026; sin licencias recientes scrapeables.
- `/dossier` con timeouts/redirecciones desde CI; solo trámites informativos.
- Transparencia urbanismo requiere Wicket AJAX para listar los 6 documentos de carpeta 7.
- Web WordPress sin sección de avisos/urbanismo indexable (no hay `pagina-aviso`).
- Plànol municipal sin PDF/imagen enlazada.
- ICV: solo zonificación PG (5 polígonos), no parcela catastral ni licencia individual.
- Municipio pequeño (622 hab., 1.10 km²) — bajo volumen en boletines.

## Adapter

- Clase: `municipio.adapters.guardamar_de_la_safor:GuardamarDeLaSaforAyuntamientoAdapter`
- Fuentes: tablón sede + PDFs web urbanismo + ICV WFS + trámites informativos sede + registro planeamiento GVA
