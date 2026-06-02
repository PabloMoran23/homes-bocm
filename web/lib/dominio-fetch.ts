/**
 * Cliente: API de dominio (Supabase) con fallback a JSON en public/data.
 */
export async function fetchDominioOrStatic(
  apiPath: string,
  staticPath: string,
  init?: RequestInit,
): Promise<Response | null> {
  for (const url of [apiPath, staticPath]) {
    try {
      const res = await fetch(url, init);
      if (res.ok) return res;
    } catch {
      /* intentar fallback */
    }
  }
  return null;
}

export async function fetchDominioJson<T>(
  apiPath: string,
  staticPath: string,
  init?: RequestInit,
): Promise<T | null> {
  const res = await fetchDominioOrStatic(apiPath, staticPath, init);
  if (!res) return null;
  try {
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
