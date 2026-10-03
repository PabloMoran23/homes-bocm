# Directorio de proyectos

La navegación pública enlaza `/proyectos` → `/proyectos/[provincia]` →
`/proyectos/[provincia]/[municipio]` → `/proyecto/[id]`. Los municipios muestran
50 fichas por página con `?pagina=N`; todas las páginas tienen enlaces HTML y
canonical propio. La página 1 redirige a la URL sin parámetro. Las páginas
inexistentes o los parámetros de página inválidos devuelven 404.

## Datos

`db/export_project_directory.py` consulta Supabase en modo de solo lectura y
genera `web/data/project-directory.json`. El archivo queda versionado, se lee
únicamente en servidor y se incluye en las funciones de Vercel mediante
`outputFileTracingIncludes`. No crea funciones SQL ni modifica tablas.

Para regenerarlo después de nuevas ingestas o investigaciones:

```bash
# SUPABASE_DB_URL o DATABASE_URL debe estar en el entorno.
.venv/bin/python db/export_project_directory.py --municipios /ruta/municipios-georef.json
```

La referencia territorial es una lista de municipios con `mun_name`, `prov_name`
y `geo_point_2d` (`lat`, `lon`). Por defecto se usa la referencia local existente
en `tools/.cache-spain-municipios-georef.json`. No se añade esa caché al repositorio.
Los nombres oficiales de la referencia determinan los slugs; conservar la misma
referencia al regenerar evita cambios de URL. El exportador informa de exclusiones
y municipios ambiguos: hay que resolverlos antes de ampliar la cobertura.

Se omiten registros sin título, los marcados como no relevantes, algunos formularios
genéricos identificables y territorios sin resolución inequívoca. Los registros
municipales sin investigación se filtran por patrones explícitos de noticias y
trámites ajenos al urbanismo (empleo público, calendario fiscal, registro de animales…).
No se exige una palabra urbanística en cada título: códigos como SU-NC-2 también
identifican actuaciones reales.
No se descartan automáticamente todos los
PDF: muchos contienen planes reales. Este filtro no sustituye una revisión
editorial del catálogo.

Los identificadores SIGMA usan guiones. Las variantes conocidas de una misma
fila (ID original y `bocm_primary_id`) redirigen a su ficha preferida. No se unen
proyectos diferentes por similitud del título. Los proyectos relacionados se
eligen dentro del municipio por programa/ámbito, tipo e investigación; no se usa
la distancia a coordenadas municipales aproximadas.

El sitemap incluye las cinco páginas principales (incluido `/proyectos`) y los proyectos investigados de su selección editorial. Regenerar el directorio no
modifica `sitemap-projects.json` ni amplía el sitemap automáticamente.

## Verificación

```bash
.venv/bin/python -m unittest discover -s db -p 'test_export_project_directory.py'
cd web
npm run verify:production
# En otra terminal, con el build anterior:
npm start -- --port 3000
node scripts/verify-project-directory.mjs http://localhost:3000
# Añadir --details para comprobar también fichas y alias de SIGMA, BOCM y portales.
```

La última comprobación recorre los enlaces HTML de Inicio y del directorio,
verifica que todas las fichas exportadas reciban enlaces, comprueba canonical y
paginación, y rechaza rutas inexistentes. No solicita las decenas de miles de
fichas a Supabase: su disponibilidad se comprueba mediante muestras separadas.

## Diseño del atlas

El directorio utiliza componentes compartidos en `web/components/directory` y un módulo CSS propio. Las páginas de provincia y municipio mantienen el mismo encabezado editorial, paleta y navegación. El buscador filtra los lugares en cliente, conservando todos los enlaces iniciales en el HTML. Los proyectos investigados pueden ocupar dos destacados; el resto se presenta como una lista, sin repetir contadores.

Los minimapas cargan MapLibre de forma diferida y reutilizan la cartografía del proyecto. `center` procede de la referencia geográfica municipal usada por el exportador. El punto municipal es una referencia del municipio, no una coordenada de cada actuación. En las vistas generales los puntos llevan al municipio correspondiente. Si la cartografía falla, el listado sigue disponible. El mapa no captura la rueda de desplazamiento.

La portada presenta una cuadrícula continua de cuatro columnas en escritorio, tres en tablet y dos en móvil. Conserva el orden geográfico del atlas, definido en `provinceOrder` dentro de `ProvinceAtlas.tsx`, sin huecos ni posiciones fijas. Cada tarjeta muestra el número de municipios con información (no el total administrativo de la provincia).

`ProvinceMiniMap.tsx` utiliza el mismo estilo cartográfico que la página provincial. Genera las miniaturas visibles secuencialmente y libera cada instancia WebGL después de capturarla, para evitar decenas de mapas activos. La atribución permanece visible bajo el conjunto. El buscador mantiene los enlaces directos a municipios al filtrar.
