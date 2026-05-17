CREATE OR REPLACE FUNCTION homes.resolve_ndp_coords(p_ndp text)
RETURNS TABLE (lat double precision, lng double precision)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT i.lat, i.lng
  FROM homes.inmueble i
  WHERE i.ndp_edificio = trim(p_ndp)
    AND i.lat IS NOT NULL
    AND i.lng IS NOT NULL
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.resolve_ndp_coords(p_ndp text)
RETURNS TABLE (lat double precision, lng double precision)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$ SELECT * FROM homes.resolve_ndp_coords(p_ndp); $$;

GRANT EXECUTE ON FUNCTION public.resolve_ndp_coords(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.resolve_ndp_coords(text) TO anon, authenticated, service_role;
