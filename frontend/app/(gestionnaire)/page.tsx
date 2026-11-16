import { redirect } from "next/navigation";

type Recherche = Record<string, string | string[] | undefined>;

function texte(valeur: string | string[] | undefined): string | null {
  if (typeof valeur === "string") return valeur;
  if (Array.isArray(valeur)) return valeur[0] ?? null;
  return null;
}

/** L'accueil envoie au portefeuille. Un retour Supabase (`?code=`,
 * `?token_hash=`, `?error=`) va d'abord sur la page du lien : ces
 * paramètres ne survivraient pas au redirect nu. Le fragment
 * `#access_token` reste dans le navigateur et est repris par
 * `RebondLienAuth`. */
export default async function AccueilGestionnaire({
  searchParams,
}: {
  searchParams: Promise<Recherche>;
}) {
  const params = await searchParams;
  const recherche = new URLSearchParams();
  for (const [cle, valeur] of Object.entries(params)) {
    const lu = texte(valeur);
    if (lu) recherche.set(cle, lu);
  }
  const brut = recherche.toString();
  const lien =
    recherche.has("code") ||
    recherche.has("token_hash") ||
    recherche.has("error") ||
    recherche.has("error_code") ||
    recherche.has("error_description");
  if (lien) redirect(`/auth/lien${brut ? `?${brut}` : ""}`);
  redirect(`/portefeuille${brut ? `?${brut}` : ""}`);
}
