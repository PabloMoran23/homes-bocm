# Montaverner — investigación portal ayuntamiento

**Municipio:** Montaverner (València / Valencia, Comunitat Valenciana)  
**Slug:** `montaverner`  
**INE:** 46167  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.montaverner.es | **Operativa** — Drupal 10 Portales (`/portada`) |
| Trámites | https://www.montaverner.es/pagina/tramits | **Operativa** — Obra Major/Menor, Informe Urbanístic, Declaració Ambiental |
| Ordenanzas | https://www.montaverner.es/pagina/ordenances-municipals | **Operativa** — PDFs ordenanzas obras, licencias, ocupación vía pública |
| Noticias | https://www.montaverner.es/noticias | Intermitente (timeouts en CI); avisos en `noticia-aviso` |
| Sede electrónica | https://montaverner.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón | https://montaverner.sedelectronica.es/board/ | **Operativo** — sin filas urbanísticas (tabla vacía) |
| Catálogo trámites | https://montaverner.sedelectronica.es/dossier | Redirect Wicket; sin histórico público |
| Consulta expedientes | https://montaverner.sedelectronica.es/expedientes | Requiere identificación |
| Registro planeamiento GVA | Carpeta `46173_MONTAVERNER` (Generalitat) | Metadatos PGOU; no scrapeado en adapter |

## Cómo se listan expedientes / licencias

- **Proyectos / normativa:** enlaces PDF en página de ordenanzas (construcciones y obras, declaración responsable, licencias ocupación, etc.).
- **Avisos:** Drupal `noticia-aviso` y eventualmente `pagina-aviso` (descubrimiento desde portada/noticias).
- **Licencias de obra:** no hay listado de concesiones; trámites informativos en web + sede (patrón Pozuelo/Benigànim).
- **Tablón sede:** HTML Wicket; columnas `class_*` cuando hay filas (actualmente vacío).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV Terramapas WFS `Planeamiento.Zonificacion` — `https://terramapas.icv.gva.es/0702_Planeamiento` (filtro `cod_ine_mun=46167`, ~11 polígonos de zonificación / normas subsidiarias).
  - No hay visor municipal ArcGIS enlazado a expedientes.
  - Registro de planeamiento autonómico (carpeta municipal) sin geometría por expediente en portal.
- **Estrategia:** paginar WFS GML3 (offsets 0–14000), asignar polígono municipal a proyectos cuyo título coincide (PGOU, ordenanza, construcción, industrial).
- **Limitaciones:** geometría de **zonificación general**, no del ámbito de cada licencia/ordenanza; tablón sin georef; web Drupal con SSL/handshake lentos desde CI (reintentos en adapter).

## Limitaciones generales

- Tablón de anuncios sin entradas urbanísticas en el momento de la investigación.
- Sin dataset público de licencias concedidas.
- Noticias/portada con timeouts frecuentes; ordenanzas y sede más estables.
- Modificación PGOU (suspensión licencias polígono La Cava, nov 2025) publicada en prensa; pendiente de aviso formal en web si no está en Drupal.

## Adapter implementado

- `municipio.adapters.montaverner:MontavernerAyuntamientoAdapter`
- Fuentes: ordenanzas Drupal + semillas ICV GVA WFS + tablón sede + trámites informativos + avisos Drupal descubiertos.
- IDs: `montaverner-lic-*` / `montaverner-proy-*` (sha256[:14]).
