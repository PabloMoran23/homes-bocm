# Mojácar — investigación portal ayuntamiento

## Municipio

- **Nombre:** Mojácar
- **Slug:** `mojacar`
- **Provincia:** Mojácar, Almería
- **CCAA:** Andalucía
- **Boletín:** BOJA (`boletin_source_id: boja`)
- **INE:** 04057

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica (espublico) | https://ayuntamientomojacar.sedelectronica.es/board/ | Tablón de anuncios (Wicket/HTML tabular) |
| Trámites sede | https://ayuntamientomojacar.sedelectronica.es/dossier | Catálogo trámites (licencias sin histórico público) |
| Web ayuntamiento (Diputación cmsdipro) | http://ayuntamiento.mojacar.es/informacion/urbanismo | PGOU, convenios, proyectos (HTML + enlaces transparencia/PDF) |
| Visor PGOU | https://palcos.tcasa.es/PGOUMojacar/ | Visor cartográfico PGOU (palcos/tcasa) |
| Perfil contratante Diputación | https://www.dipalme.org/Servicios/cmsdipro/index.nsf/tablon_view_perfil.xsp?p=mojacar | Enlace al tablón sede |
| Turismo (no urbanismo) | https://www.mojacar.es | WordPress turístico; no usar como fuente principal |

**Nota:** `mojacar.sedelectronica.es` responde “Sede Electrónica Indeterminada”; la sede correcta es `ayuntamientomojacar.sedelectronica.es`.

## Cómo se listan expedientes / proyectos

1. **Tablón sede:** filas HTML `<tr>` con clases `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. Enlaces a `/preview-document/{uuid}`. Procedimientos “Actuaciones Urbanísticas”, “Urbanismo”, etc.
2. **Web urbanismo:** secciones PGOU (aprobaciones 2021/2022), convenios urbanísticos, otros proyectos (paseo marítimo, residencia mayores, EDAR, variante costera). Enlaces a transparencia sede, PDFs Diputación y páginas cmsdipro.
3. **Sin API JSON** de expedientes; scrape determinista HTML.

## Licencias de obra

- No hay dataset público de concesiones históricas.
- Edictos de licencias/actividad aparecen en el tablón sede cuando se publican.
- Trámites informativos en `/dossier` (comunicación previa, licencias).
- El adapter incluye filas informativas del tablón + trámites (patrón Cómpeta/Vera).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor PGOU: `https://palcos.tcasa.es/PGOUMojacar/` — GeoServer `Mojacar` en `palcos.tcasa.es:8443` (capas WMS: `actuaciones_suelo_urbano`, `clasificacion`, `planes_especiales`, etc.). **WFS deshabilitado** en el servicio (`Service WFS is disabled`).
  - WFS Diputación Almería: `https://app.dipalme.org/geoserver/urbanismo/ows` — capa `urbanismo:v_siu_ambitos_o_sectores` filtrada `cod_ine='04057'` (11 sectores: PERI01, UA02, UE01, …).
- **Estrategia:** enriquecer proyectos cuyo título menciona un sector del WFS Diputación (`_fetch_geometry_for_title`). Visor PGOU como fila metadata sin polígono por expediente.
- **Limitaciones:** visor tcasa sin WFS/API por código de expediente; tablón/PDF sin georef directa; matching sector↔título heurístico (parcial).

## Limitaciones generales

- Tablón sede muestra ~10 anuncios recientes (sin paginación visible).
- Web cmsdipro mezcla menú lateral global (no filtrado por sección).
- SSL sede: certificado válido; `insecure_ssl: true` por compatibilidad con otros adapters espublico.
- `www.mojacar.es` es portal turístico, no sede urbanística.
