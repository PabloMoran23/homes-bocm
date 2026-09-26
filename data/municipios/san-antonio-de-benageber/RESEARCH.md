# San Antonio de Benagéber — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `san-antonio-de-benageber` |
| INE | 46903 |
| Provincia | Valencia / Comunitat Valenciana |
| Boletín | DOGV (`dogv`, 2 entradas BOCM) |

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.sanantoniodebenageber.es | Drupal Adaptive Theme; **timeout** desde red del agente (217.13.85.35) |
| Urbanismo (web) | https://www.sanantoniodebenageber.es/es/pagina/urbanismo | Horarios y contacto urbanismo@sabenageber.com |
| Formularios URBA | https://www.sanantoniodebenageber.es/es/pagina/documentos-para-descargar | URBA-01..12 (licencias, actividad) |
| Sede electrónica | https://sanantoniodebenageber.sedelectronica.es | espublico gestiona (Wicket/YUI) |
| Tablón de anuncios | https://sanantoniodebenageber.sedelectronica.es/board | Edictos y anuncios públicos |
| Portal transparencia urbanismo | https://sanantoniodebenageber.sedelectronica.es/transparency/57255e6b-c9fd-4ce4-8629-c2ef8b15a670/ | Sección 7 — Urbanismo, Obras Públicas y Medio Ambiente |
| Catálogo trámites | https://sanantoniodebenageber.sedelectronica.es/dossier | Licencias vía sede (sin listado histórico) |

## Cómo se listan expedientes / proyectos

1. **ICV WFS InventarioSuSuz:** 31 sectores/unidades de ejecución del PGOU (Montesano, R-1..R-11, T-1, UE-7, etc.) con polígonos en WGS84.
2. **Portal transparencia (espublico):** carpeta «7. Urbanismo…» con subcarpetas:
   - 7.1 Planeamiento Urbanístico (21 docs)
   - 7.3 Normativa Urbanística (17)
   - 7.4 Obras Públicas e Infraestructuras (0)
   - Documentos cargados vía **Wicket AJAX**; no hay listado HTML estático.
3. **Tablón `/board`:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `preview-document/{uuid}`. Ejemplo activo: modificación puntual 16 TER R1-R6 Montesano (exp. 4627/2025).

## Cómo se publican licencias

- No hay listado público histórico de licencias concedidas.
- Formularios URBA en web municipal (obra menor, licencia obras, actividad, etc.).
- Trámites vía sede (`/dossier`); consulta expedientes requiere identificación.
- Tablón publica edictos puntuales; en la investigación no había licencias de obra activas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Parámetros: `outputFormat=GML3`, `srsName=EPSG:4326`, paginación `STARTINDEX`/`count=200`
  - Filtro en cliente: `cod_ine_mun=46903`
  - Campos: `pp`, `ue`, `clasificacion`, `uso`, `f_aprob`, `f_public`
- **Estrategia:** descargar WFS paginado (~70 s), convertir `posList` GML → GeoJSON Polygon WGS84; enriquecer filas tablón por tokens sector (MONTESANO, R-6, UE-7, …).
- **Limitaciones:**
  - Web municipal inaccesible desde entorno cloud (timeout TCP); sede sí responde.
  - WFS no admite `CQL_FILTER` fiable; requiere paginar todo el dataset CV.
  - Portal transparencia con docs AJAX/Wicket; no scrapeable sin reverse del protocolo.
  - Licencias del tablón son PDFs sin georreferencia.
  - No hay visor urbanístico municipal público enlazable (solo ICV regional).

## Limitaciones generales

- `sabenageber.com` (IP 75.101.138.47) también con timeout TLS desde el agente.
- Tablón mayoritariamente no urbanístico (nombramientos, etc.).
- Entidades singulares: Colinas De San Antonio, Montesano (sectores PGOU).

## Adapter

- `municipio.adapters.san_antonio_de_benageber:SanAntonioDeBenageberAyuntamientoAdapter`
- Fuentes: ICV WFS + tablón sede + carpetas transparencia (metadatos) + páginas informativas licencias/formularios URBA.
