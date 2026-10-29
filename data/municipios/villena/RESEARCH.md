# Villena — investigación portal ayuntamiento

**Municipio:** Villena (Alicante, Comunitat Valenciana)  
**Slug:** `villena`  
**INE:** 03140 (P0314000A)  
**Boletín:** sin entrada asociada en cola (`bocm_count: 0`)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.villena.es | Operativa — WordPress (Divi) |
| Urbanismo / licencias | https://www.villena.es/urbanismo-licencias-de-obras-disciplina-urbanistica-y-patrimonio/ | Operativa — PGOU PDFs, contacto |
| Sede Sedipualba | https://sede.villena.es | Operativa — ASP.NET Sedipualba (dominio propio, no `*.sedipualba.es`) |
| Tablón de anuncios | https://sede.villena.es/tablondeanuncios/ | Operativa |
| Tablón RSS | https://sede.villena.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista |
| Catálogo URB | https://sede.villena.es/catalogoservicios.aspx?ambito=&area=1915 | URB001–URB014 |
| Tablón STA (legacy) | https://185.97.171.196/sta/…PTS2_TABLON | Enlace en sede; IP directa, no usado en adapter |
| Tablón anterior | sede — «anterior a 1 de marzo de 2025» | Histórico CSV |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Planeamiento aprobado | ICV WFS `InventarioSuSuz` + `Planeamiento.Zonificacion` (filtro cliente `cod_ine_mun=03140`) |
| Documentación PGOU | PDFs enlazados en página de urbanismo (memorias, normas, PE casco histórico) |
| Noticias urbanísticas | WordPress — búsqueda `?s=urbanismo`, `planeamiento`, etc. |
| Tablón | Sedipualba RSS — mayoría administrativa/personal (oct 2026); filtro área «URBANISMO» (id 1241) no aísla bien en HTML |
| Expedientes ciudadano | SEGEX / carpeta ciudadana — sin acceso público sin certificado |

## Cómo se publican licencias

- Trámites URB en sede (licencia urbanística, declaración responsable, intervención patrimonio, etc.) — solo formularios, sin registro histórico público
- Tablón electrónico para edictos; pocas licencias de obra recientes en RSS
- Atención presencial / cita vía info.urbanismo@villena.es

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capas `InventarioSuSuz` y `Planeamiento.Zonificacion`, salida GML3 / EPSG:4326
  - Filtro en cliente por `cod_ine_mun=03140` (CQL del servicio no fiable)
- **Estrategia:** paginación WFS (`STARTINDEX` / `startIndex`); matching título↔denominación sector; polígonos PGOU vía Zonificacion
- **Limitaciones:**
  - Sin visor municipal ArcGIS público identificado
  - Geometría ICV = sectores/zonificación aprobada, no parcela ni expediente de licencia
  - Escaneo completo InventarioSuSuz es lento (~minutos)
  - Tablón sin geometría enlazable

## Limitaciones generales

- PGOU vigente de 1992 en web; revisión en curso (noticias 2025–2026)
- RSS tablón sin urbanismo frecuente; proyectos desde WP + PDFs PGOU + ICV
- Acceso a expedientes administrativos requiere certificado / corporación (SCR001)

## Adapter implementado

- `municipio.adapters.villena:VillenaAyuntamientoAdapter`
- Fuentes: tablón RSS + catálogo URB + PDFs PGOU + noticias WP + ICV WFS (SUZ+Zon)
- IDs: `villena-lic-*` / `villena-proy-*` (sha256[:14])
