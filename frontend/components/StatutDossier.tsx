import { cn } from "cn";

export type StatutDossierEtat = "a-traiter" | "a-jour" | "sans-compte" | "cloture";

/** DESIGN.md § Statut d'un dossier (`statut-dossier`) : point de 8px + libellé.
 * Vocabulaire propre aux dossiers du portefeuille, distinct des badges
 * d'écriture : un dossier n'a jamais de badge. Le point est décoratif, le
 * libellé porte toujours le sens (`signal` ne distingue jamais seul). */
const ETATS: Record<StatutDossierEtat, { libelle: string; point: string }> = {
  "a-traiter": { libelle: "À traiter", point: "bg-signal" },
  "a-jour": { libelle: "À jour", point: "bg-success" },
  "sans-compte": { libelle: "Sans compte", point: "bg-faint" },
  cloture: { libelle: "Clôturé", point: "bg-closed" },
};

export function StatutDossier({ etat, className }: { etat: StatutDossierEtat; className?: string }) {
  const { libelle, point } = ETATS[etat];
  return (
    <span
      data-etat={etat}
      className={cn("inline-flex items-center gap-2 text-[13px] leading-[1.38] font-semibold text-ink", className)}
    >
      <span aria-hidden="true" className={cn("size-2 shrink-0 rounded-full", point)} />
      {libelle}
    </span>
  );
}
