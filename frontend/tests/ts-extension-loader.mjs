export async function resolve(specifier, context, nextResolve) {
  try {
    return await nextResolve(specifier, context);
  } catch (error) {
    if (specifier.startsWith(".")) return nextResolve(`${specifier}.ts`, context);
    throw error;
  }
}
