# Bornos — investigación portal ayuntamiento

Municipio: **Bornos** (`bornos`), provincia Cádiz, Andalucía. Boletín: BOJA (4 entradas BOCM).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://www.bornos.es | Joomla + Phoca Download |
| PBOM | https://www.bornos.es/pbom-bornos | Documentos planeamiento (aprobación inicial 2025) |
| Sede electrónica | https://sede.bornos.es | Liferay (tema ecadiz / Diputación Cádiz) |
| Tablón / edictos | https://sede.bornos.es/edictos/publico?idOrgan=11 | EPICSA Struts (SPA edictos) |
| Tablón Liferay | https://sede.bornos.es/tablon-electronico-de-anuncios-y-edictos | Redirige a EPICSA |
| Trámites | https://sede.bornos.es/tramites-disponibles | Catálogo (DR obras tramite 5540) |
| SituaDIFusión | https://ws132.juntadeandalucia.es/situadifusion/... | Planeamiento general aprobado (codfigura 21839) |
| Gobierno abierto Dip. Cádiz | https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?entidadId=801 | Catálogo transparencia (sin datasets urbanísticos GIS) |

**Nota:** `bornos.sedelectronica.es` devuelve página genérica "seleccione su sede"; la sede activa es `sede.bornos.es`.

## Expedientes / proyectos

1. **PBOM (web municipal):** Joomla Phoca Download con categorías Memoria, Normativa urbanística, Cartografía, Anexos, Resumen ejecutivo. Descargas vía `?download=ID:slug`. Certificado aprobación inicial PBOM (nov 2025).
2. **Edictos EPICSA:** Tabla HTML en `/edictos/publico?idOrgan=11` con ~77 edictos. Mayoría personal/empleo; pocos urbanismo (ej. calificación ambiental punto limpio 2016). Sin API JSON pública.
3. **SituaDIFusión:** Enlace desde web municipal al planeamiento general aprobado digitalizado (raster escaneado, no listado de expedientes).
4. **Consulta expedientes:** Requiere autenticación en sede; no hay listado público de expedientes urbanísticos individuales.

## Licencias de obra

- **Sin listado histórico** de licencias concedidas en portal público.
- Trámite **Declaración responsable para la ejecución de obras** (tramite 5540) en sede.
- Edictos EPICSA pueden incluir notificaciones de licencia/actividad (pocos en histórico).
- Adapter devuelve páginas informativas de tablón + trámites (patrón Pozuelo/Cómpeta).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - PBOM cartografía (`/pbom-bornos/6-cartografia`): categoría sin archivos GIS descargables.
  - SituaDIFusión Junta de Andalucía: planeamiento digitalizado raster (codfigura 21839), sin WFS/ArcGIS REST enlazable a expediente.
  - Diputación Cádiz gobierno abierto: sin capas WFS urbanísticas para Bornos.
  - Sede EPICSA: solo PDFs de edictos, sin coordenadas.
- **Estrategia:** No aplicable; orquestador usará centroide municipio + jitter.
- **Limitaciones:** Sin visor urbanístico municipal; PBOM reciente sin geometría vectorial pública; edictos mayoría no georreferenciados.

## Limitaciones técnicas

- Sede Liferay ecadiz compartida con otros ayuntamentos gaditanos; edictos vía EPICSA SPA.
- `insecure_ssl: true` no requerido (certificados válidos).
- Paginación edictos: tabla completa en una página (~77 registros).
- Web municipal y sede accesibles desde CI sin bloqueo.
