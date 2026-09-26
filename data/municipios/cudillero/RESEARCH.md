# Cudillero — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal | https://www.cudillero.es | Liferay Digital Experience Platform (i-cast) |
| Normativa | https://www.cudillero.es/normativa | Ordenanzas fiscales y urbanísticas (PDFs /documents/) |
| Tablón de anuncios | https://www.cudillero.es/tablon | Asset publisher Liferay; mayormente empleo/contratación |
| Sede electrónica | https://cudillero.sede.e-ayuntamiento.es | Plataforma e-ayuntamiento; timeout frecuente en CI |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Cudillero | `busquedaConsulta?method=listPublico&idConcejo=21&estado=V` | 44 instrumentos vigentes (HTML tabla paginada, 3 páginas) |
| Visor urbanístico | https://sigvisor.asturias.es/visorurbanismo | Mapa interactivo RPGUR (ArcGIS) |
| Visor legacy | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/ | Mapa interactivo HTML/JS |

## Cómo se listan expedientes

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=21` (CUDILLERO). Tabla HTML paginada (15/página, 44 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado. Codificación ISO-8859-1.

2. **Web municipal Liferay:** Página `/normativa` con PDFs de ordenanzas (fiscales y disciplina urbanística vía BOPA). Tablón `/tablon` sin expedientes urbanísticos individuales. Sin sección dedicada de urbanismo/planeamiento en el menú principal.

3. **Sede electrónica:** Trámites urbanísticos presenciales/online; sin listado público de expedientes ni licencias concedidas.

## Cómo se publican licencias

- **No hay tablón público de licencias de obra** en la web municipal ni en la sede accesible.
- Ordenanza de declaración responsable publicada en BOPA (2024-05200.pdf) enlazada desde normativa.
- El adapter devuelve páginas informativas de trámites urbanísticos (normativa + sede).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%CUDILLERO%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - Resultado: 1 polígono municipal (NSPM CUDILLERO, id 1774)
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 1/44 instrumentos con polígono en WFS (ámbito municipal NSPM completo).
  - Instrumentos de desarrollo (revisiones parciales, modificaciones) sin geometría individual en WFS público.
  - Visor ArcGIS sigvisor.asturias.es requiere interacción manual; no API directa por expediente.
  - Sede electrónica inaccesible para consulta automatizada.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- 44 instrumentos vigentes — detalle RPGUR por instrumento (~15s scrape total).
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.
- Tablón sin licencias de obra publicadas.
