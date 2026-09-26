# Muro de Alcoy — investigación portal ayuntamiento

## Identificación

| Campo | Valor |
|-------|--------|
| Slug | `muro-de-alcoy` |
| Nombre oficial | Muro de Alcoy (val. *Muro d'Alcoi*) |
| INE | 03092 |
| Provincia | Alicante / Alacant |
| CIF | P0309200D |

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.vilademuro.net |
| Urbanismo — Planejament | https://www.vilademuro.net/el-ayuntamiento/concejalias/urbanisme/planejament/ |
| Transparencia urbanismo | https://www.vilademuro.net/portal-de-transparencia/urbanisme-i-medi-ambient/ |
| Sede electrónica | https://vilademuro.sedelectronica.es |
| Tablón de anuncios | https://vilademuro.sedelectronica.es/board |
| Catálogo trámites (web) | https://www.vilademuro.net/es/catalogo-de-procedimientos/ |
| Consulta expedientes | https://vilademuro.sedelectronica.es/expedientes (requiere Cl@ve) |

**Nota:** El dominio `www.murodealcoy.es` no resuelve DNS; la web oficial es `vilademuro.net` (registro GVA entidades locales).

## CMS y formato de datos

### Web municipal (WordPress + GeneratePress)

- Páginas estáticas con enlaces a PDF/ZIP en `/wp-content/uploads/`.
- Sección **Planejament** con memoria PGOU, normas urbanísticas, planos y edictos de modificaciones puntuales.
- No hay visor propio del ayuntamiento enlazado a expedientes; el planeamiento se publica como documentación descargable.

### Sede electrónica (espublico gestiona / Wicket)

- Tablón HTML con filas `<tr>` y celdas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- Documentos en `/preview-document/{uuid}`.
- Categorías relevantes: **Urbanisme**, procedimientos **Planejament General**.
- Sin listado público histórico de licencias concedidas; las licencias se tramitan por sede.

## Licencias de obra

- No hay dataset ni tabla pública de concesiones.
- El tablón puede publicar edictos puntuales (p. ej. herencias, no licencias masivas).
- Trámites: catálogo en sede + página de procedimientos en la web.
- El adapter devuelve páginas informativas del tablón y catálogo, más filas del tablón que coincidan con patrones de licencia.

## Proyectos / planeamiento

| Fuente | Contenido |
|--------|-----------|
| ICV WFS `InventarioSuSuz` | ~20 ámbitos SUZ/UE del municipio (geometría poligonal) |
| Web Planejament | PDFs PGOU, modificaciones, planos |
| Tablón sede | Anuncios BOP/DOGV de aprobaciones (p. ej. modificación puntual PGOU nº 5) |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS ICV: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `InventarioSuSuz`
  - Filtro cliente: `cod_ine_mun = 03092`
  - Campos: `pp`, `ue`, `clasificacion`, `f_aprob`, geometría GML `ms:msGeometry`
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
- **Estrategia:** Descarga paginada WFS (STARTINDEX) + filtro INE; enriquecimiento de filas del tablón/web por coincidencia de sector/UE en el título.
- **Limitaciones:**
  - No hay visor municipal con enlace expediente↔polígono.
  - WFS no filtra bien por CQL en servidor; se filtra en cliente.
  - Documentos del tablón son PDF sin georreferencia directa.
  - Consulta de expedientes urbanísticos requiere autenticación.

## Limitaciones generales

- Web bilingüe (valenciano/castellano); rutas pueden variar `/es/`.
- Tablón con pocas filas visibles por página (paginación Wicket).
- SSL sede: certificado válido (no requiere `insecure_ssl`).
