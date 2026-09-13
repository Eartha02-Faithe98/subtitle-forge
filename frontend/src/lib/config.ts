const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl(
  configuredValue: string | undefined = process.env.NEXT_PUBLIC_API_BASE_URL,
): string {
  const value = configuredValue?.trim() || DEFAULT_API_BASE_URL;

  try {
    const url = new URL(value);
    const hasPath = url.pathname !== "/" && url.pathname !== "";
    const isUnsafe =
      !["http:", "https:"].includes(url.protocol) ||
      Boolean(
        url.username || url.password || url.search || url.hash || hasPath,
      );

    if (isUnsafe) {
      throw new Error("unsafe URL");
    }

    return url.origin;
  } catch {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL must be an explicit HTTP(S) origin",
    );
  }
}
