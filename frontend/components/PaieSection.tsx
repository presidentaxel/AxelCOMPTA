"use client";

// Président assimilé salarié (SASU, SAS) : il recopie son bulletin, que
// produit son logiciel de paie. AxeLCompta le passe en comptabilité, sans
// calculer la paie ni déposer la DSN. Son virement net se catégorise
// ensuite « Ma rémunération », le paiement à l'URSSAF « Mes cotisations
// sociales ».
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  fetchAvecAuthChauffeur,
  saisirBulletinChauffeur,
} from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import type { BulletinVue } from "@/lib/types";

const CHAMPS = [
  ["brut", "Salaire brut"],
  ["salariales", "Cotisations salariales"],
  ["patronales", "Cotisations patronales"],
  ["pas", "Prélèvement à la source"],
] as const;

function enCentimes(valeur: string): number {
  return Math.round(Number(valeur.replace(",", ".") || "0") * 100);
}

export function PaieSection({ dossierId }: { dossierId: string }) {
  const [bulletins, setBulletins] = useState<BulletinVue[]>([]);
  const [mois, setMois] = useState("");
  const [montants, setMontants] = useState<Record<string, string>>({});
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    fetchAvecAuthChauffeur<BulletinVue[]>(`/dossiers/${dossierId}/bulletins`)
      .then(setBulletins)
      .catch(() => setBulletins([]));
  }, [dossierId]);

  async function enregistrer() {
    setEnCours(true);
    setErreur(null);
    try {
      const bulletin = await saisirBulletinChauffeur(dossierId, {
        mois,
        brut_cts: enCentimes(montants.brut ?? ""),
        cotisations_salariales_cts: enCentimes(montants.salariales ?? ""),
        cotisations_patronales_cts: enCentimes(montants.patronales ?? ""),
        prelevement_a_la_source_cts: enCentimes(montants.pas ?? ""),
      });
      setBulletins((liste) => [...liste, bulletin]);
      setMois("");
      setMontants({});
    } catch (exception) {
      setErreur(
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "Échec de l'enregistrement.",
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="mt-8">
      <h2 className="text-sm font-medium text-ink">Ma paie</h2>
      <p className="mt-1 text-xs text-subtle">
        Recopiez chaque bulletin de votre logiciel de paie. AxeLCompta le comptabilise ; il ne
        calcule pas la paie et ne dépose pas la DSN.
      </p>
      {bulletins.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {bulletins.map((bulletin) => (
            <li key={bulletin.mois} className="flex justify-between">
              <span className="text-subtle">{bulletin.mois}</span>
              <span className="tabular-nums text-ink">
                brut {formatMontant(bulletin.brut_cts)} · net {formatMontant(bulletin.net_a_payer_cts)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 grid grid-cols-1 gap-2">
        <Input
          type="month"
          className="h-11 text-base"
          value={mois}
          onChange={(evenement) => setMois(evenement.target.value)}
        />
        {CHAMPS.map(([cle, libelle]) => (
          <Input
            key={cle}
            inputMode="decimal"
            className="h-11 text-base"
            placeholder={`${libelle} (€)`}
            value={montants[cle] ?? ""}
            onChange={(evenement) =>
              setMontants((actuels) => ({ ...actuels, [cle]: evenement.target.value }))
            }
          />
        ))}
      </div>
      <Button className="mt-3 h-11" disabled={enCours || !mois || !montants.brut} onClick={enregistrer}>
        {enCours ? "Enregistrement…" : "Enregistrer le bulletin"}
      </Button>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </section>
  );
}
