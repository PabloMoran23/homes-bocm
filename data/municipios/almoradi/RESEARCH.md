# Almoradí — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.almoradi.es | WordPress (tema Almoradí / townblock) |
| Urbanismo | https://www.almoradi.es/areas/urbanismo/ | Enlaces a instancias, normas subsidiarias, PGE |
| PGE | https://www.almoradi.es/areas/urbanismo/plan-general-estructural/ | PDFs volumen I, catálogo, estudios, NN.UU. |
| Normas subsidiarias | https://www.almoradi.es/areas/urbanismo/normas-subsidiarias-de-planeamiento-municipal/ | Memoria y anexos PDF |
| Instancias | https://www.almoradi.es/areas/urbanismo/instancias-urbanismo/ | Modelos PDF (licencias, comunicaciones) |
| Sede electrónica | https://almoradi.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón | https://almoradi.sedelectronica.es/board/ | Tabla HTML (`class_name`, `class_folderCode`, …) + `preview-document/{uuid}` |
| Trámites | https://almoradi.sedelectronica.es/dossier | Catálogo (carga lenta; no usado como semilla principal) |
| Transparencia | https://almoradi.sedelectronica.es/transparency/ | Bloque «territorio, urbanismo y medio ambiente» (documentos PDF) |

## Listado de expedientes / proyectos

- **Tablón sede:** filas con expediente, procedimiento, categoría, descripción y enlace a PDF en `preview-document`. En la muestra consultada (nov 2026) predominan anuncios no urbanísticos (padrón, empleo); los edictos de urbanismo aparecen de forma esporádica.
- **Web Urbanismo:** documentación estática del PGE y normas subsidiarias (PDFs en `/wp-content/uploads/`).
- **ICV InventarioSuSuz:** capa regional con unidades de actuación del término municipal (55 features `cod_ine_mun=03009`).

## Licencias

- No hay registro público estructurado de concesiones de licencia en el tablón (patrón habitual CV).
- Modelos descargables en «Instancias Urbanismo» (solicitud licencia, cambio de uso, comunicación previa, etc.) — trámites informativos, no listado de obras concedidas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Generalitat `https://terramapas.icv.gva.es/0702_Planeamiento` — layer `InventarioSuSuz`, filtro `CQL_FILTER=cod_ine_mun='03009'`, GML3 / EPSG:4326.
  - Visor ICV: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
- **Estrategia:** ingestar polígonos WFS como proyectos de planeamiento (`origen: icv_wfs`); intentar enriquecer filas del tablón/web por coincidencia de código UE en el título.
- **Limitaciones:** geometría no enlazada 1:1 a expedientes del tablón; licencias sin coords salvo jitter municipal; tablón muestra solo ~10 anuncios recientes sin paginación pública obvia. Los polígonos `InventarioSuSuz` con `cod_ine_mun=03009` en ICV aparecen desplazados (~38.71°N) respecto al término de Almoradí; el adapter no adjunta `geom_geojson` fuera del bbox municipal documentado.

## Limitaciones técnicas

- Sede `dossier` responde con mucha latencia desde el agente.
- Tablón sin API JSON; scrape HTML determinista.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
