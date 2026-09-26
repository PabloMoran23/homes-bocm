# Arcabuey — investigación portal ayuntamiento

**Municipio:** Arcabuey (Jaén, Andalucía)  
**Slug:** `arcabuey`  
**INE:** 23002  
**Boletín:** BOJA (`boja`, 1 entrada en histórico de cola)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.arcabuey.es | **Inaccesible** — sin respuesta HTTP desde CI |
| Sede eprinsa | https://sede.eprinsa.es/arcabuey | **Parcial** — SPA Ember responde 200; APIs entidad 404 |
| Tablón eprinsa | https://sede.eprinsa.es/arcabuey/tablon-de-edictos | **SPA** — componente wec-bulletins; sin API pública |
| Trámites eprinsa | https://sede.eprinsa.es/arcabuey/tramites | SPA sin listado scrapeable |
| Sede espublico | https://arcabuey.sedelectronica.es | **No configurada** — «Sede Electrónica Indeterminada» |
| Tablón espublico | https://arcabuey.sedelectronica.es/board/ | Mismo mensaje de sede indeterminada |
| Transparencia local | https://arcabuey.transparencialocal.gob.es | Redirige al directorio nacional (sin portal propio) |
| SITUADIFUSION | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento digitalizado regional (Jaén) |
| VITUA | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ | Cartografía LISTA/PGOU por municipio |
| Tablón Dip. Jaén | https://sede.dipujaen.es/Tablon | Edictos provinciales (filtro Arcabuey sin resultados en CI) |

## Cómo se listan expedientes

- **Ayuntamiento:** no hay portal municipal operativo ni sede configurada con tablón scrapeable.
- **eprinsa:** plataforma compartida (Diputación Córdoba APIs) con skin genérico; entidad `arcabuey` sin configuración en `apisede`.
- **espublico gestiona:** dominio reservado pero instancia no vinculada al municipio.
- **Regional (SITUA/VITUA):** instrumentos de planeamiento aprobados digitalizados por la Junta; consulta interactiva por municipio, sin API REST por expediente municipal.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Las licencias deberían publicarse en tablón de la sede electrónica cuando esté operativa.
- El adapter documenta páginas informativas de trámites (eprinsa + espublico) sin filas de concesión histórica.

## Proyectos / planeamiento

| Origen | Contenido |
|--------|-----------|
| SITUADIFUSION | Consulta de planeamiento general aprobado (Jaén → Arcabuey) |
| VITUA | Cartografía urbanística regional |
| Tablón Dip. Jaén | Posibles edictos provinciales (ninguno filtrado para Arcabuey en CI) |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): clasificación/calificación del suelo por municipio; sin campo expediente del ayuntamiento.
  - SITUADIFUSION: documentación escaneada de instrumentos; sin query por código de expediente municipal.
  - Diputación Jaén IDE (`ide.dipujaen.es`): WFS no accesible en rutas públicas probadas; Jaén capital y Linares excluidos en documentación de referencia.
- **Estrategia:** no hay visor municipal ArcGIS ni WFS enlazable a expedientes. El orquestador aplicará centroide municipio + jitter (`centroid: [38.0197, -2.7719]`).
- **Limitaciones:**
  - Web municipal caída.
  - Sedes electrónicas sin datos públicos estructurados.
  - Tablón eprinsa SPA sin API REST.
  - Sin geometría por expediente.

## Limitaciones generales

- Municipio muy pequeño (Sierra de Segura) con infraestructura digital mínima.
- `sede.eprinsa.es/arcabuey` parece placeholder (metadatos genéricos Córdoba).
- Nominatim/OSM sin entrada para el núcleo urbano.

## Adapter implementado

- `municipio.adapters.arcabuey:ArcabueyAyuntamientoAdapter`
- Fuentes: referencias SITUA/VITUA/tablon provincial + páginas informativas sede (licencias).
