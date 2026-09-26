# Mogente (Moixent) — investigación portal ayuntamiento

**Municipio:** Mogente / Moixent (Valencia, Comunitat Valenciana)  
**Slug:** `mogente`  
**Boletín:** DOGV (`dogv`, 3 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.moixent.es | **Operativa** — Drupal 10 Portales municipales (tema `portales`, Matomo site 190) |
| Urbanismo | https://www.moixent.es/es/pagina/urbanismo | Noticia PGOU digitalizado (subvención GVA 2024) + enlace transparencia |
| Impresos urbanismo | https://www.moixent.es/es/pagina/impresos-urbanismo | Formularios PDF licencias obra, DR, segregación, compatibilidad |
| Plano calles | https://www.moixent.es/es/pagina/plano-calles | Plano estático (no visor interactivo) |
| Sede electrónica | https://moixent.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://moixent.sedelectronica.es/board | **Operativa** — tabla HTML (~10 filas; incluye PUAM urbanismo) |
| Transparencia planeamiento | https://moixent.sedelectronica.es/transparency/991457ff-f304-40d5-8815-2b9820cb5a4c/ | Documentación PGOU digitalizada |
| Catálogo trámites | https://moixent.sedelectronica.es/dossier | Trámites sin histórico público de concesiones |
| Consulta expedientes | https://moixent.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |

## Avisos Drupal (urbanismo / planeamiento)

El ayuntamiento publica instrumentos de planeamiento como **noticia-aviso** (`/es/noticia-aviso/...`), enlazados desde la home:

| Slug | Título | Tipo |
|------|--------|------|
| `plan-urbano-actuacion-municipal-puam` | Plan Urbano de Actuación Municipal (PUAM) | plan de actuación |
| `plan-movilidad-urbana-sostenible-pmus` | Plan de Movilidad Urbana Sostenible (PMUS) | movilidad |
| `alegaciones-contra-proyecto-central-fotovoltaica-para-estacion-bombeo-moixent` | Central fotovoltaica estación bombeo | instalación energética |

- **CMS:** Drupal 10 Portales (`/themes/portales`).
- **Listado:** sin JSON:API pública; el adapter descubre enlaces `noticia-aviso` en `/es` + semillas configuradas.
- **Documentos:** PDFs embebidos en avisos (`/sites/www.moixent.es/files/...`).

## Tablón sede (espublico gestiona)

- Plataforma Wicket espublico gestiona (misma familia que Benigànim, Enguera).
- Columnas: `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- Contenido relevante (ago 2026): **aprobación inicial modificación PUAM** (exp. 45/2026, categoría Urbanismo, procedimiento Disposicions Normatives).
- Paginación AJAX «Mostrar más»; adapter parsea primera página.

## Licencias de obra

- No hay dataset público de concesiones históricas de licencia de obra.
- Formularios descargables en `/es/pagina/impresos-urbanismo` (licencia edificación, DR, segregación, etc.).
- Trámites de obra vía sede `/dossier` (sin listado histórico).
- El adapter incluye páginas informativas del tablón, impresos y catálogo de trámites (patrón Benigànim/Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - ICV WFS `Planeamiento.Zonificacion` (https://terramapas.icv.gva.es/0702_Planeamiento): filtros CQL por `cod_ine_mun=46134` no aplican en servidor; bbox sobre Moixent (~-0.85,38.80,-0.70,38.92) devuelve 0 features.
  - Visor GVA regional (https://visor.gva.es): capas de zonificación CCAA, no enlazables a expedientes del tablón municipal.
  - Plano calles municipal: imagen/PDF estático sin georreferencia por expediente.
- **Estrategia:** tablón y avisos son PDF/HTML sin polígonos; el orquestador aplicará centroide municipio + jitter (`centroid: [38.872, -0.765]`).
- **Limitaciones:** sin ArcGIS/WFS municipal con campo expediente; ICV no expone geometría filtrable fiable para este municipio.

## Limitaciones generales

- Web municipal puede responder lentamente desde CI (requiere reintentos).
- Consulta de expedientes requiere login.
- Transparencia sede puede requerir sesión para algunos documentos.
- Sin geometría enlazable por expediente.

## Adapter implementado

- `municipio.adapters.mogente:MogenteAyuntamientoAdapter`
- Fuentes: avisos Drupal + tablón sede + urbanismo/transparencia + trámites informativos.
- IDs: `mogente-lic-*` / `mogente-proy-*` (sha256[:14]).
