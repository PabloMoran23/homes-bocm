import { cache } from "react";
import type { UbicacionFicha } from "@/lib/ubicacion";
import { normalizeDireccion } from "@/lib/direccion";
import { getSupabaseServer } from "@/lib/supabase/server";

/** Una sola RPC por request (metadata + page comparten la misma promesa). */
export const loadUbicacionFicha = cache(async (ndp: string): Promise<UbicacionFicha | null> => {
  const supabase = getSupabaseServer();
  if (!supabase) {
    return null;
  }

  const { data, error } = await supabase.rpc("get_ubicacion_ficha", {
    p_ndp: ndp.trim(),
  });

  if (error) {
    console.error("get_ubicacion_ficha:", error.message);
    throw new Error(`No se pudo cargar la ficha (${error.message})`);
  }

  if (!data) {
    return null;
  }

  const ficha = data as UbicacionFicha;
  if (ficha.inmueble?.direccion) {
    ficha.inmueble.direccion = normalizeDireccion(ficha.inmueble.direccion);
  }
  return ficha;
});
