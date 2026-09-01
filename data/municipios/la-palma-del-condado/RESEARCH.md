# La Palma del Condado — investigación portal ayuntamiento

**Municipio:** La Palma del Condado (Huelva, Andalucía)  
**Slug:** `la-palma-del-condado`  
**BOJA:** 2 entradas en histórico regional

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.lapalmadelcondado.es | **Inaccesible** — error SSL (`UNEXPECTED_EOF_WHILE_READING`); HTTP devuelve 502 |
| Sede electrónica | https://lapalmadelcondado.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://lapalmadelcondado.sedelectronica.es/board/ | Operativa — tabla HTML Wicket (~10 filas visibles) |
| Transparencia | https://lapalmadelcondado.sedelectronica.es/transparency/ | Carpeta «8. INFORMACIÓN URBANÍSTICA…» (9 docs) vía AJAX Wicket |
| Trámites (`/dossier`) | https://lapalmadelcondado.sedelectronica.es/dossier | Redirección infinita (302 loop) — no usable |
| Consulta expedientes | https://lapalmadelcondado.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| PGOU Junta (SITUA) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor PGOU regional (sin API por expediente) |

## Cómo se listan expedientes / proyectos

1. **Tablón sede (`/board/`):** tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Procedimientos relevantes: «Actuaciones Urbanísticas», «Planeamiento General», «Calidad Ambiental» (edictos IP). Enlaces a `/preview-document/{uuid}`. Paginación «Mostrar más» vía Wicket AJAX (solo primera página scrapeada).
2. **Transparencia sede:** carpeta «8. INFORMACIÓN URBANÍSTICA, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con 9 documentos; navegación por subcarpetas requiere peticiones AJAX Wicket — no replicado en adapter.
3. **Web municipal:** no accesible en el entorno del agente (SSL roto); no se puede verificar sección urbanismo ni PDFs estáticos.

Ejemplos encontrados en tablón (ago 2026): modificación PGOU nº 20 (aprobación inicial BOP), proyecto urbanización «LA PALMA-2» (definitivo), edicto información pública ambiental.

## Licencias de obra

- **No hay listado público** de licencias concedidas.
- El tablón puede publicar edictos de licencia puntuales (filtro por regex).
- Trámites informativos referenciados en sede (`/dossier`, `/expedientes`) — dossier con redirect loop; expedientes autenticados.
- Adapter devuelve páginas informativas de referencia + edictos del tablón si aparecen.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUA Junta de Andalucía — visor PGOU municipal sin API REST/WFS enlazable a código de expediente.
  - Web municipal — inaccesible (SSL).
  - Sede espublico — documentos PDF sin coordenadas ni visor integrado.
  - No se encontró visor ArcGIS/WFS municipal público.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [37.3861, -6.5547]`).
- **Limitaciones:** planeamiento publicado como PDF en tablón; web corporativa caída; transparencia AJAX no accesible sin sesión Wicket.

## Limitaciones generales

- Tablón paginado (~10 filas visibles); adapter captura página actual.
- Web corporativa con certificado/servidor defectuoso — no scrapeable.
- `/dossier` con bucle de redirección.
- Licencias históricas no publicadas en web abierta.
- SSL sede: válido; `insecure_ssl: true` por consistencia con otros adapters espublico.

## Adapter

- `municipio.adapters.la_palma_del_condado:LaPalmaDelCondadoAyuntamientoAdapter`
- IDs: `la-palma-del-condado-lic-*` / `la-palma-del-condado-proy-*` (sha256[:14]).
