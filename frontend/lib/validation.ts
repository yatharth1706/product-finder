const AMAZON_HOSTS = ["amazon.in", "amazon.com", "amzn.in", "amzn.to", "amzn.eu"];

/** Quick check before calling the API. The backend does the real validation. */
export function amazonUrlError(value: string): string | null {
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    return "Paste a full link, starting with https://";
  }
  const host = url.hostname.toLowerCase();
  const isAmazon = AMAZON_HOSTS.some((h) => host === h || host.endsWith(`.${h}`));
  return isAmazon ? null : "That is not an Amazon link";
}
