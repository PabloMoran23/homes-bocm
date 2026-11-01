# Alaquàs — investigación portal ayuntamiento

Municipio: **Alaquàs** (`alaquas`) — Comunitat Valenciana, provincia Valencia. INE **46004**.

## Fuentes base

| Recurso | URL | Notas |
|---------|-----|--------|
| Web municipal | https://www.alaquas.org | CMS propio; documentación urbanística en `/monografies/` y `/ajuntament/1/` |
| Sede electrónica | https://alaquas.sedelectronica.es | **espublico gestiona** (Wicket) |
| Tablón sede | https://alaquas.sedelectronica.es/board | Tabla HTML con `preview-document/{uuid}` |
| Urbanisme (sede) | https://alaquas.sedelectronica.es/citizen-service/ddd2e6a6-94d6-43c8-8c4b-661d76dbe3d6 | Área Urbanisme i Activitats |
| Trámites OAC (legacy) | https://www.alaquas.org/oac/menu.asp?i=1 | Listado de solicitudes (licencias obra, vados, etc.) |
| Tablón web legacy | https://www.alaquas.org/web/transparencia/tablon.asp?i=1 | Enlace desde menú transparencia |

## Listado de expedientes / anuncios

- **Tablón sede (`/board`)**: filas con columnas Document(o), Expedient(e), Procediment(o), Categoria, Descripció, Data de publicació. Enlace al PDF en `class_name` → `/preview-document/{uuid}`.
- Sin RSS público tipo sedipualba; primera página muestra ~10 anuncios recientes (paginación Wicket no expuesta en HTML estático).
- Procedimientos urbanísticos observados: certificados/informes urbanísticos, aprobaciones de ordenanzas, anuncios de aprobación (p. ej. documento CSV `3A26L4DL3AKRKM6LXYQYDC4QE`, dic-2025).

## Licencias

- No hay dataset abierto de concesiones georreferenciadas.
- Concesiones puntuales aparecen en tablón (p. ej. resoluciones, certificados).
- Trámites informativos: OAC (`licencia de obras`, ocupación vía pública, vados, zanjas) y catálogo sede (acceso `/dossier` redirige en bucle desde algunos clientes).
- Adapter: filas del tablón filtradas por regex + páginas informativas (tablón sede, área urbanisme).

## Documentación urbanística (web)

Semillas estáticas (accesibles cuando la web responde):

- PGOU 2015: https://www.alaquas.org/monografies/pgou2015/
- Mod. PGOU 2: https://www.alaquas.org/monografies/urbanismo-documento_mod2pgou/
- Mod. PGOU 3: https://www.alaquas.org/monografies/urbanismo-documento_mod3pgou/
- Sector VI: https://www.alaquas.org/monografies/urbanismo-sector6/
- Sector VII: https://www.alaquas.org/monografies/urbanismo-sector7/
- PUAM, plan movilidad, Barranco de la Saleta — enlaces desde https://www.alaquas.org/ajuntament/1/

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `https://terramapas.icv.gva.es/0702_Planeamiento` — capas `Planeamiento.Zonificacion`, `ms:InventarioSuSuz`; filtro por `cod_ine_mun=46004` al parsear GML.
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
- **Estrategia:** paginar WFS (STARTINDEX) y cargar polígonos municipales; cruce por tokens sector/UE/PP en título del tablón o semilla; centroides WGS84.
- **Limitaciones:**
  - WFS no enlaza expediente concreto del tablón espublico; matching heurístico.
  - Anuncios de licencia en tablón suelen ser PDF sin georef.
  - `www.alaquas.org` devuelve **403** desde el entorno cloud del agente; semillas web se mantienen como URLs de referencia.

## Limitaciones generales

- Tablón sede: solo página inicial scrapeable sin sesión AJAX.
- Boletín regional: sin `boletin_source_id` en cola (`bocm_count: 0`).
- Sin visor municipal ArcGIS propio identificado; dependencia de capas autonómicas ICV.
