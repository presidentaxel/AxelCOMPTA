/** AXE-851 : ce que le gestionnaire voit des comptes bancaires qui attendent
 * le choix du dirigeant. Des nombres et une date, jamais les comptes. */

export type AvecComptesAChoisir = {
  comptes_a_choisir?: number;
  comptes_a_choisir_depuis?: string | null;
  operations_en_attente_de_choix?: number;
};

export function attendUnChoixDeCompte(dossier: AvecComptesAChoisir): boolean {
  return (dossier.comptes_a_choisir ?? 0) > 0;
}

function dateCourte(iso: string): string {
  const [annee, mois, jour] = iso.split("-");
  return `${jour}/${mois}/${annee}`;
}

/** Une ligne sous l'entreprise, ou `null` s'il n'y a rien à choisir. */
export function phraseComptesAChoisir(dossier: AvecComptesAChoisir): string | null {
  const nombre = dossier.comptes_a_choisir ?? 0;
  if (nombre < 1) return null;
  const comptes =
    nombre === 1
      ? "Un compte bancaire attend le choix du dirigeant"
      : `${nombre} comptes bancaires attendent le choix du dirigeant`;
  const depuis = dossier.comptes_a_choisir_depuis
    ? ` depuis le ${dateCourte(dossier.comptes_a_choisir_depuis)}`
    : "";
  const operations = dossier.operations_en_attente_de_choix ?? 0;
  const suite =
    operations === 0
      ? ""
      : operations === 1
        ? " : 1 opération n'entre pas en comptabilité"
        : ` : ${operations} opérations n'entrent pas en comptabilité`;
  return `${comptes}${depuis}${suite}.`;
}

/** Le bandeau au-dessus de la liste, ou `null` si aucune entreprise n'attend. */
export function bandeauComptesAChoisir(dossiers: readonly AvecComptesAChoisir[]): string | null {
  const nombre = dossiers.filter(attendUnChoixDeCompte).length;
  if (nombre === 0) return null;
  const qui =
    nombre === 1
      ? "Une entreprise a un compte bancaire"
      : `${nombre} entreprises ont un compte bancaire`;
  return (
    `${qui} dont le dirigeant n'a pas dit s'il sert à l'activité. ` +
    "Ses opérations n'entrent pas en comptabilité tant qu'il n'a pas répondu dans son espace."
  );
}
