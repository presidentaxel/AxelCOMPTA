/** Logos des plateformes (Uber, Bolt, Heetch) via Logo.dev.
 * La clé publiable (`pk_`) est faite pour le navigateur. La clé secrète
 * (`sk_`) reste dans le backend. */

const DOMAINES: Record<string, string> = {
  uber: "uber.com",
  bolt: "bolt.eu",
  heetch: "heetch.com",
  freenow: "free-now.com",
  "free now": "free-now.com",
  marcel: "marcel.cab",
  allocab: "allocab.com",
  lecab: "lecab.fr",
};

/** URL du logo, ou `null` si la clé publiable n'est pas configurée. */
export function urlLogo(nom: string, cle = process.env.NEXT_PUBLIC_LOGO_DEV_PUBLISHABLE_KEY): string | null {
  const token = cle?.trim();
  const marque = nom.trim();
  if (!token || !marque) return null;
  const domaine = DOMAINES[marque.toLowerCase()];
  const chemin = domaine ?? `name/${encodeURIComponent(marque)}`;
  const params = new URLSearchParams({ token, size: "64", format: "png" });
  return `https://img.logo.dev/${chemin}?${params}`;
}
