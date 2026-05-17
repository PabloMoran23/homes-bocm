import type { UbicacionFicha } from "@/lib/ubicacion";
import { getSupabaseServer } from "@/lib/supabase/server";

export async function loadUbicacionFicha(ndp: string): Promise<UbicacionFicha | null> {
  const supabase = getSupabaseServer();
  if (!supabase) {
    return null;
  }

  const { data, error } = await supabase.rpc("get_ubicacion_ficha", {
    p_ndp: ndp.trim(),
  });

  if (error) {
    console.error("get_ubicacion_ficha:", error.message);
    return null;
  }

  if (!data) {
    return null;
  }

  return data as UbicacionFicha;
}
