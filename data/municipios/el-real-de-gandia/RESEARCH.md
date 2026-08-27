# El Real de Gandia — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `el-real-de-gandia` |
| INE | 46205 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.realdegandia.es | Timeout SSL handshake desde CI (Adaptive Theme) |
| Urbanismo | https://www.realdegandia.es/es/pagina/urbanismo | Timeout CI — normas subsidiarias, planes parciales, trámites obra |
| Normas urbanísticas | https://www.realdegandia.es/es/pagina/normas-urbanisticas | Timeout CI — PDFs y planos consulta |
| Transparencia urbanística | https://www.realdegandia.es/es/transparencia/informacion-urbanistica | Timeout CI — PGOU, PUAM, PLPIF, autoprotección |
| PDF normas subsidiarias | https://www.realdegandia.es/sites/www.realdegandia.es/files/files/tramites/urbanismo/normas_urbanisticas_-_real_de_gandia.pdf | Timeout CI (misma origen) |
| Sede electrónica | https://realdegandia.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://realdegandia.sedelectronica.es/board/ | Operativa — tabla HTML preview-document |
| Catálogo trámites | https://realdegandia.sedelectronica.es/dossier | Operativa |
| Consulta expedientes | https://realdegandia.sedelectronica.es/expedientes | Requiere autenticación |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo (referencia) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / obras | Trámites sede (DR obras, compatibilidad urbanística) + formularios web urbanismo |
| Planeamiento | Normas subsidiarias y planes parciales (Germanias, Vernisa, Novoperfil) en web |
| Transparencia | Portal transparencia — PUAM, PLPIF, planes autoprotección, información pública PP |
| Tablón | Sede `/board/` — edictos recientes (mayoría no urbanísticos en agosto 2026) |

### Tablón sede (agosto 2026)

- Sancionador infracción normativa (exp. 1248/2025) — no licencia
- Lista jurado popular (exp. 996/2024) — no urbanismo
- Ordenanza taxa autorizaciones actividades (16/2015) — normativa fiscal actividades

## Cómo se publican licencias

- Sin dataset histórico público de concesiones con coordenadas
- Edictos puntuales en tablón sede cuando procede notificación
- Trámites telemáticos: declaración responsable obras, licencias mayores/menores (web + dossier)
- Consulta expedientes requiere identificación Cl@ve

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46205`
  - Visor GVA: capa `spaicv0702_plan_zonificacion`
- **Estrategia:** escaneo paginado WFS GeoJSON (`EPSG:4326`); matching título↔`denominaci`; instrumento «Plan general» con polígono municipal
- **Limitaciones:**
  - Solo zonificación PGOU en ICV (1 instrumento único con geometría); sin parcela catastral ni licencia individual
  - Sin visor municipal ArcGIS identificado
  - Web municipal inaccesible desde agente CI (SSL timeout)
  - Planes parciales Germanias/Vernisa/Novoperfil solo como PDF/HTML sin GIS enlazable

### Instrumentos ICV (cod_ine_mun=46205)

| Expediente | Denominación | Geometría |
|------------|--------------|-----------|
| 19940614 | Plan general | MultiPolygon (WFS) |

## Limitaciones generales

- Web www.realdegandia.es: handshake SSL timeout en CI (~30s); seeds estáticos en adapter
- Tablón: pocas filas visibles sin paginación AJAX útil
- Escaneo ICV WFS completo ~2 min; cache en memoria por ejecución
- Sede `insecure_ssl: true` (certificado caducado en cadena)
- Provincia en `queue.yaml` usa formato largo; manifest usa `Valencia`

## Adapter implementado

- `municipio.adapters.el_real_de_gandia:ElRealDeGandiaAyuntamientoAdapter`
- Fuentes: tablón sede + ICV WFS + páginas web/transparencia (estáticas) + trámites informativos sede
