const AMAZON_HOSTS = ["amazon.in", "amazon.com", "amzn.in", "amzn.to", "amzn.eu"];

/** "amazon.in/dp/B0F7X5FC43" -> "https://amazon.in/dp/B0F7X5FC43". */
export function normalizeAmazonUrl(value: string): string {
  const trimmed = value.trim();
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

/** Quick check before calling the API. The backend does the real validation. */
export function amazonUrlError(value: string): string | null {
  if (!value.trim()) return "Paste an Amazon product link";
  let url: URL;
  try {
    url = new URL(normalizeAmazonUrl(value));
  } catch {
    return "That doesn't look like a link";
  }
  const host = url.hostname.toLowerCase();
  const isAmazon = AMAZON_HOSTS.some((h) => host === h || host.endsWith(`.${h}`));
  return isAmazon ? null : "That is not an Amazon link";
}
