"use client";

// Président assimilé salarié (SASU, SAS) : il recopie son bulletin, que
// produit son logiciel de paie. AxeLCompta le passe en comptabilité, sans
// calculer la paie ni déposer la DSN. Son virement net se catégorise
// ensuite « Ma rémunération », le paiement à l'URSSAF « Mes cotisations
// sociales ».
import { useEffect, useState } from "react";

import { Aide } from "@/components/Aide";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  fetchAvecAuthChauffeur,
  saisirBulletinChauffeur,
} from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { lireEuros } from "@/lib/saisie-chauffeur";
import type { BulletinVue } from "@/lib/types";

const CHAMPS = [
  ["brut", "Salaire avant retenues", "Le brut : le salaire avant ce qui est prélevé."],
  [
    "salariales",
    "Retenues sur le salaire",
    "Les cotisations salariales : retraite, maladie, prélevées sur le brut.",
  ],
  [
    "patronales",
    "Charges de la société",
    "Les cotisations patronales : ce que la société paie en plus du salaire.",
  ],
  ["pas", "Impôt prélevé", "Le prélèvement à la source : l'impôt sur le revenu retenu sur le salaire."],
] as const;

function lireEurosOuZero(saisie: string): number | string {
  const texte = saisie.replace(/[\s\u00a0\u202f]/g, "").replace(",", ".");
  if (texte === "" || texte === "0" || texte === "0.0" || texte === "0.00") return 0;
  const lu = lireEuros(saisie);
  return "centimes" in lu ? lu.centimes : lu.message;
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
    const brut = lireEuros(montants.brut ?? "");
    const salariales = lireEurosOuZero(montants.salariales ?? "");
    const patronales = lireEurosOuZero(montants.patronales ?? "");
    const pas = lireEurosOuZero(montants.pas ?? "");
    const illisible = [brut, salariales, patronales, pas].find((lu) => typeof lu === "string");
    if (typeof illisible === "string" || !("centimes" in brut)) {
      setErreur(typeof illisible === "string" ? illisible : "Indiquez le salaire avant retenues.");
      return;
    }
    setEnCours(true);
    setErreur(null);
    try {
      const bulletin = await saisirBulletinChauffeur(dossierId, {
        mois,
        brut_cts: brut.centimes,
        cotisations_salariales_cts: salariales as number,
        cotisations_patronales_cts: patronales as number,
        prelevement_a_la_source_cts: pas as number,
      });
      setBulletins((liste) => [...liste, bulletin]);
      setMois("");
      setMontants({});
    } catch (exception) {
      setErreur(
        phrasePourChauffeur(
          exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
            ? exception.message
            : "Échec de l'enregistrement.",
        ),
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="mt-8">
      <h2 className="text-sm font-medium text-ink">Ma paie</h2>
      <p className="mt-1 text-sm text-subtle">
        Recopiez chaque bulletin de votre logiciel de paie. AxeLCompta le range dans les comptes.
        Il ne calcule pas la paie et n&apos;envoie pas la déclaration sociale.
        <Aide texte="La DSN (déclaration sociale nominative) part chaque mois vers les organismes sociaux, depuis votre logiciel de paie." />
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
      <div className="mt-3 grid grid-cols-1 gap-2 text-sm">
        <label className="block text-subtle">
          Mois du bulletin
          <Input
            type="month"
            aria-label="Mois du bulletin"
            className="mt-1 h-11 text-base"
            value={mois}
            onChange={(evenement) => setMois(evenement.target.value)}
          />
        </label>
        {CHAMPS.map(([cle, libelle, aide]) => (
          <label key={cle} className="block text-subtle">
            {libelle}
            <Aide texte={aide} />
            <Input
              inputMode="decimal"
              aria-label={libelle}
              placeholder="€"
              className="mt-1 h-11 text-base"
              value={montants[cle] ?? ""}
              onChange={(evenement) =>
                setMontants((actuels) => ({ ...actuels, [cle]: evenement.target.value }))
              }
            />
          </label>
        ))}
      </div>
      <Button className="mt-3 h-11" disabled={enCours || !mois || !montants.brut} onClick={enregistrer}>
        {enCours ? "Enregistrement…" : "Enregistrer le bulletin"}
      </Button>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </section>
  );
}
