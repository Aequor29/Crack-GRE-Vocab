export function configuredApiOrigin(): string | null {
  const configuredUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configuredUrl) {
    return null;
  }

  try {
    const url = new URL(configuredUrl);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    ) {
      return null;
    }
    return url.origin;
  } catch {
    return null;
  }
}
