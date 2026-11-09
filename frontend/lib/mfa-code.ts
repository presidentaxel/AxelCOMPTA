/** Ce qui se décide sans réseau dans la double authentification (AXE-812). */

export type Facteur = { id: string; factor_type: string; status: string };

/** Six chiffres, espaces tolérés (« 123 456 » recopié d'une application). */
export function codeNormalise(saisie: string): string | null {
  const code = saisie.replace(/\s+/g, "");
  return /^\d{6}$/.test(code) ? code : null;
}

/** Le facteur TOTP déjà vérifié, s'il y en a un. */
export function facteurVerifie(facteurs: readonly Facteur[]): Facteur | null {
  return facteurs.find((f) => f.factor_type === "totp" && f.status === "verified") ?? null;
}
