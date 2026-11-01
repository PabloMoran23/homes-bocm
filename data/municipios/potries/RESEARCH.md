# Potries — investigación portal ayuntamiento

**Municipio:** Potries (València / Valencia, Comunitat Valenciana)  
**Slug:** `potries`  
**INE:** 46125  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://potries.org | **Operativa** — WordPress (Enfold) |
| Urbanismo (área municipal) | https://potries.org/es/organizacion-municipal/urbanismo-servicios-y-seguridad/ | Noticias y contacto (C/ Boamit 28) |
| Portal transparencia | https://potries.portal-transparencia.com/?lang=es | **Operativo** |
| Planeamiento vigente | https://potries.portal-transparencia.com/planejament/?lang=es | PDF catálogo patrimonial (nov 2021) |
| Planeamiento en tramitación | https://potries.portal-transparencia.com/planejament-tramitacio/?lang=es | Sin documentos publicados |
| Ordenanzas | https://potries.portal-transparencia.com/ordenances/?lang=es | Tabla HTML + PDFs `/uploads/ordenances/` |
| Tablón (transparencia) | https://potries.portal-transparencia.com/tauler/?lang=es | Enlace a sede |
| Sede electrónica | https://potries.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón sede | https://potries.sedelectronica.es/board/ | HTML Wicket; filas mayoría subvenciones/personal |
| Catálogo trámites | https://potries.sedelectronica.es/dossier | Sin histórico público de concesiones |
| Consulta expedientes | https://potries.sedelectronica.es/expedientes | Requiere identificación |

## Cómo se listan expedientes / licencias

- **Proyectos / normativa:** tablas en portal de transparencia (fecha + título + enlace PDF). Ordenanzas urbanísticas (espacio urbano, vía pública, estética inmuebles, etc.) y catálogo de bienes protegidos en planeamiento.
- **Noticias urbanísticas:** entradas WordPress enlazadas desde la sección de urbanismo (p. ej. peatonalización calles, PLPIF).
- **Licencias de obra:** no hay listado de concesiones; trámites vía sede (patrón CV habitual).
- **Tablón sede:** columnas `class_*` (documento, expediente, procedimiento, fecha); sin filas de licencias en el momento de la investigación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV Terramapas WFS `Planeamiento.Zonificacion` — `https://terramapas.icv.gva.es/0702_Planeamiento` (`CQL_FILTER=cod_ine_mun='46125'`): PGOU, planes parciales (Nenieto, sector C-16, etc.).
  - No hay visor municipal ArcGIS enlazado por expediente.
- **Estrategia:** semillas desde WFS + enriquecimiento por palabras clave en títulos de ordenanzas/planeamiento.
- **Limitaciones:** polígonos de **zonificación general**, no del ámbito de cada licencia; tablón sin georef; planeamiento en tramitación vacío.

## Limitaciones generales

- Sin dataset público de licencias concedidas.
- Portal transparencia y sede con SSL gestionado (adapter usa `insecure_ssl` si hace falta en CI).
- Municipio pequeño: pocos instrumentos de planeamiento publicados en web.

## Adapter implementado

- `municipio.adapters.potries:PotriesAyuntamientoAdapter`
- Fuentes: transparencia (ordenanzas + planejament) + ICV GVA WFS + tablón sede + páginas informativas de trámites + avisos WordPress.
- IDs: `potries-lic-*` / `potries-proy-*` (sha256[:14]).
