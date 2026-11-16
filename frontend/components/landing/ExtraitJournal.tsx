import {
  EXTRAIT_JOURNAL,
  formaterCentimes,
  totauxJournal,
  type LigneJournal,
} from "@/lib/landing-contenu";

const ENTETE = "px-2.5 py-2 text-[11px] font-semibold uppercase tracking-[0.06em]";
const CELLULE = "px-2.5 py-3";

function Montant({ centimes }: { centimes: number | null }) {
  return <span className="tabular-nums">{centimes === null ? " " : formaterCentimes(centimes)}</span>;
}

function Ligne({ ligne }: { ligne: LigneJournal }) {
  return (
    <tr className={ligne.aImputer ? "border-b border-hairline bg-highlight-wash" : "border-b border-hairline"}>
      <td className={`${CELLULE} pl-[18px] text-muted`}>{ligne.numero}</td>
      <td className={CELLULE}>
        {ligne.libelle}
        {ligne.aImputer && (
          <span className="ml-1.5 rounded-full bg-pending-subtle px-2 py-px text-[11px] font-semibold text-pending-ink">
            À imputer
          </span>
        )}
      </td>
      <td className={`${CELLULE} text-body`}>{ligne.compte}</td>
      <td className={`${CELLULE} text-right`}>
        <Montant centimes={ligne.debitCentimes} />
      </td>
      <td className={`${CELLULE} pr-[18px] text-right`}>
        <Montant centimes={ligne.creditCentimes} />
      </td>
    </tr>
  );
}

/** Un extrait de grand livre inventé : le domaine (comptes du PCG, compte
 * d'attente 471, totaux égaux) montre ce que fait AxeL sans exposer un vrai
 * dossier. Les montants sont des centimes entiers, affichés en colonnes
 * tabulaires alignées à droite (DESIGN.md › Montants). */
export function ExtraitJournal() {
  const { debit, credit } = totauxJournal(EXTRAIT_JOURNAL.lignes);
  return (
    <figure className="m-0 flex min-w-0 flex-col gap-2.5">
      <div className="overflow-hidden rounded-lg border border-border bg-canvas">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-[18px] py-3.5">
          <figcaption className="text-xs font-semibold uppercase tracking-[0.06em] text-muted">
            {EXTRAIT_JOURNAL.titre}
          </figcaption>
          <span className="text-xs text-muted">{EXTRAIT_JOURNAL.periode}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-[13px] text-ink">
            <thead className="bg-surface-soft text-subtle">
              <tr>
                <th scope="col" className={`${ENTETE} pl-[18px] text-left`}>N°</th>
                <th scope="col" className={`${ENTETE} text-left`}>Libellé</th>
                <th scope="col" className={`${ENTETE} text-left`}>Compte</th>
                <th scope="col" className={`${ENTETE} text-right`}>Débit</th>
                <th scope="col" className={`${ENTETE} pr-[18px] text-right`}>Crédit</th>
              </tr>
            </thead>
            <tbody>
              {EXTRAIT_JOURNAL.lignes.map((ligne, rang) => (
                <Ligne key={rang} ligne={ligne} />
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-border-strong font-semibold">
                <td colSpan={3} className={`${CELLULE} pl-[18px]`}>
                  <span className="inline-flex items-center gap-2">
                    Total
                    <span className="rounded-full bg-validated-subtle px-2 py-px text-[11px] font-semibold text-validated">
                      {debit === credit ? "Équilibré" : "Déséquilibré"}
                    </span>
                  </span>
                </td>
                <td className={`${CELLULE} text-right`}>
                  <Montant centimes={debit} />
                </td>
                <td className={`${CELLULE} pr-[18px] text-right`}>
                  <Montant centimes={credit} />
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
      <p className="text-xs text-muted">{EXTRAIT_JOURNAL.legende}</p>
    </figure>
  );
}
