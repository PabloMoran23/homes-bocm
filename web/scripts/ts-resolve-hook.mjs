export async function resolve(specifier, context, nextResolve) {
  if (
    (specifier.startsWith("./") || specifier.startsWith("../")) &&
    !specifier.endsWith(".ts") &&
    !specifier.endsWith(".mjs") &&
    !specifier.endsWith(".js")
  ) {
    try {
      return await nextResolve(`${specifier}.ts`, context);
    } catch {
      /* fall through */
    }
  }
  return nextResolve(specifier, context);
}
