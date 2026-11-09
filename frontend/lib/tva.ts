/** AXE-805 : ce que l'écran « Ma TVA » décide sans réseau. */

export type LigneCa3 = { numero: string; libelle: string; centimes: number };

export type PeriodeTva = {
  cle: string;
  debut: string;
  fin: string;
  echeance: string | null;
  lignes: LigneCa3[];
  due_cts: number;
  credit_cts: number;
  declaree: boolean;
  a_traiter: number;
};

export type TvaVue = {
  periodicite: "mensuelle" | "trimestrielle" | null;
  jour_echeance: number | null;
  periodes: PeriodeTva[];
};

const MOIS = [
  "janvier", "février", "mars", "avril", "mai", "juin",
  "juillet", "août", "septembre", "octobre", "novembre", "décembre",
];

/** « mars 2026 », « 1er trimestre 2026 ». */
export function nomPeriode(cle: string): string {
  const [annee, partie] = cle.split("-");
  if (partie?.startsWith("T")) {
    const rang = partie.slice(1);
    return `${rang === "1" ? "1er" : `${rang}e`} trimestre ${annee}`;
  }
  return `${MOIS[Number(partie) - 1] ?? partie} ${annee}`;
}

/** La période à montrer d'abord : la plus ancienne terminée et pas déclarée,
 * sinon la dernière terminée, sinon la première. */
export function periodeParDefaut(periodes: readonly PeriodeTva[], aujourdHui: string): PeriodeTva | null {
  const terminees = periodes.filter((p) => p.fin < aujourdHui);
  return (
    terminees.find((p) => !p.declaree) ?? terminees.at(-1) ?? periodes[0] ?? null
  );
}

/** Pour le gestionnaire : une ligne sans montant, ou `null`. */
export function phraseTvaADeclarer(cle: string | null | undefined, echeance: string | null | undefined): string | null {
  if (!cle) return null;
  if (!echeance) return `TVA de ${nomPeriode(cle)} à déclarer (échéance à régler par le dirigeant).`;
  const [a, m, j] = echeance.split("-");
  return `TVA de ${nomPeriode(cle)} à déclarer avant le ${j}/${m}/${a}.`;
}
