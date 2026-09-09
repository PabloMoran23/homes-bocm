# Benicarló, Vinaròs, Benijófar — investigación portal ayuntamiento

**Entrada de cola compuesta:** tres municipios de la Comunitat Valenciana (Castellón + Alicante).  
**Slug:** `benicarlo-vinaros-benijofar`  
**Boletín:** DOGV (`dogv`, 1 entrada agregada en histórico)

| Municipio | Provincia | INE | Web | Sede |
|-----------|-----------|-----|-----|------|
| Benicarló | Castellón | 12018 | https://www.benicarlo.org | https://benicarlo.sedipualba.es |
| Vinaròs | Castellón | 12138 | https://www.vinaros.es | https://vinaros.sedelectronica.es |
| Benijófar | Alicante | 03012 | https://www.benijofar.es | https://benijofar.sedelectronica.es |

## URLs base y páginas semilla

### Benicarló

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.benicarlo.org | **Operativa** — PHP propietario (no Drupal) |
| Sede electrónica | https://benicarlo.sedipualba.es | **Operativa** — sedipualba/Diputación Albacete |
| Tablón de anuncios | https://benicarlo.sedipualba.es/tablondeanuncios/default.aspx | **Operativa** — filtro «Urbanisme» (id=427) |
| RSS tablón | https://benicarlo.sedipualba.es/tablondeanuncios/tablon_rss.aspx | **Operativa** |
| Sede espublico | https://benicarlo.sedelectronica.es/board | **Indeterminada** — página de selección de sede (no usar) |

### Vinaròs

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.vinaros.es | **Operativa** — Drupal 8 |
| Sede electrónica | https://vinaros.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://vinaros.sedelectronica.es/board | **Operativa** — categoría «Actuacions Urbanístiques» |
| Urbanismo (visor) | https://urbanisme.vinaros.es | **Operativa** — Drupal 8 subdominio |
| Planeamiento municipal | https://urbanisme.vinaros.es/es/contenido/planeamiento-urbanistico-municipal | ZIP planeamiento (sep 2026) |

### Benijófar

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.benijofar.es | **Operativa** — WordPress + GeneratePress |
| Sede electrónica | https://benijofar.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://benijofar.sedelectronica.es/board | **Operativa** — categorías «Planeamiento General» / «Urbanismo» |
| Tablón web (WP) | https://www.benijofar.es/category/noticias/tablon/feed/ | RSS con anuncios municipales |

## Cómo se listan expedientes

- **Benicarló:** tablón sedipualba con tabla HTML + RSS (`anuncio.aspx?id=`). Categoría Urbanisme en filtro. Sin visor urbanístico municipal público enlazado.
- **Vinaròs:** tablón espublico (tabla Wicket, `preview-document/{uuid}`) + subdominio `urbanisme.vinaros.es` con documentación PGOU en ZIP.
- **Benijófar:** tablón espublico + noticias WP categoría «Tablón». Expedientes de planeamiento en categoría «Planeamiento General».

## Licencias de obra

- No hay dataset histórico público con coordenadas en ninguno de los tres municipios.
- Concesiones aparecen como edictos en tablón cuando se publican.
- Adapter incluye páginas informativas de trámites (catálogo sede) por municipio.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` + `Planeamiento.Zonificacion`: `https://terramapas.icv.gva.es/0702_Planeamiento` (`outputFormat=GML3`, `srsName=EPSG:4326`). Filtro cliente por `cod_ine_mun` (12018, 12138, 03012).
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
  - Vinaròs: `urbanisme.vinaros.es` publica ZIP de planeamiento sin API GIS enlazable a expedientes.
- **Estrategia:** descargar ámbitos SU/SUZ del inventario regional por INE; emparejar por código sector/UE en títulos de tablón cuando sea posible.
- **Limitaciones:**
  - Inventario regional informativo (sin enlace directo expediente-tabla).
  - Benicarló: `www.benicarlo.es` no resuelve; usar `benicarlo.org`.
  - Tablones espublico: solo primera página HTML (sin paginación AJAX).
  - PGOU/ZIP sin georreferencia embebida en metadatos del tablón.

## Adapter implementado

- `municipio.adapters.benicarlo_vinaros_benijofar:BenicarloVinarosBenijofarAyuntamientoAdapter`
- Fuentes por municipio: sedipualba RSS (Benicarló) / espublico board (Vinaròs, Benijófar) + ICV WFS + semillas web (urbanisme.vinaros.es, WP tablón Benijófar).
