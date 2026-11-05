"use client";

// Président assimilé salarié (SASU, SAS) : il recopie son bulletin, que
// produit son logiciel de paie. AxeLCompta le passe en comptabilité, sans
// calculer la paie ni déposer la DSN. Son virement net se catégorise
// ensuite « Ma rémunération », le paiement à l'URSSAF « Mes cotisations
// sociales ».
import { useCallback, useEffect, useState } from "react";

import { Aide } from "@/components/Aide";
import { EtatErreur } from "@/components/EtatChargement";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  fetchAvecAuthChauffeur,
  saisirBulletinChauffeur,
} from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import { messageVisible } from "@/lib/messages";
import { lireEuros } from "@/lib/saisie-chauffeur";
import type { BulletinVue } from "@/lib/types";

const CHAMPS = [
  ["brut", "Salaire avant charges"],
  ["salariales", "Charges retenues sur le salaire"],
  ["patronales", "Charges payées par la société"],
  ["pas", "Impôt retenu sur le salaire"],
] as const;

export function PaieSection({ dossierId }: { dossierId: string }) {
  const [lecture, setLecture] = useState<"en_cours" | "pret" | "erreur">("en_cours");
  const [messageEchec, setMessageEchec] = useState("");
  const [bulletins, setBulletins] = useState<BulletinVue[]>([]);
  const [mois, setMois] = useState("");
  const [montants, setMontants] = useState<Record<string, string>>({});
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    let annule = false;
    fetchAvecAuthChauffeur<BulletinVue[]>(`/dossiers/${dossierId}/bulletins`)
      .then((liste) => {
        if (annule) return;
        setBulletins(liste);
        setLecture("pret");
      })
      .catch((exception: unknown) => {
        if (annule) return;
        setMessageEchec(messageVisible(exception, "Impossible de charger les bulletins."));
        setLecture("erreur");
      });
    return () => {
      annule = true;
    };
  }, [dossierId]);

  useEffect(() => charger(), [charger]);

  async function enregistrer() {
    setEnCours(true);
    setErreur(null);
    try {
      if (lecture !== "pret") return;
      const brut = lireEuros(montants.brut ?? "");
      if ("message" in brut) {
        setErreur(brut.message);
        return;
      }
      const salariales = lireEurosOuZero(montants.salariales ?? "");
      const patronales = lireEurosOuZero(montants.patronales ?? "");
      const pas = lireEurosOuZero(montants.pas ?? "");
      if (typeof salariales === "string" || typeof patronales === "string" || typeof pas === "string") {
        setErreur("Écrivez chaque montant avec une virgule, par exemple 1 000,50.");
        return;
      }
      const bulletin = await saisirBulletinChauffeur(dossierId, {
        mois,
        brut_cts: brut.centimes,
        cotisations_salariales_cts: salariales,
        cotisations_patronales_cts: patronales,
        prelevement_a_la_source_cts: pas,
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
      <p className="mt-1 text-sm text-subtle">
        Recopiez chaque bulletin de votre logiciel de paie. AxeLCompta le comptabilise ; il ne
        calcule pas la paie et ne dépose pas la déclaration de paie
        <Aide tactile texte="La DSN : la déclaration que votre logiciel de paie envoie déjà. AxeLCompta ne s'en charge pas." />
        .
      </p>
      {lecture === "en_cours" && <Squelette className="mt-3 h-11 w-full" />}
      {lecture === "erreur" && (
        <EtatErreur
          message={messageEchec}
          onReessayer={() => {
            setLecture("en_cours");
            charger();
          }}
        />
      )}
      {lecture === "pret" && bulletins.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {bulletins.map((bulletin) => (
            <li key={bulletin.mois} className="flex justify-between">
              <span className="text-subtle">{bulletin.mois}</span>
              <span className="tabular-nums text-ink">
                avant charges {formatMontant(bulletin.brut_cts)} · reçu{" "}
                {formatMontant(bulletin.net_a_payer_cts)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {lecture === "pret" && (
      <div className="mt-3 grid grid-cols-1 gap-2 text-sm">
        <label className="text-subtle" htmlFor="mois-bulletin">
          Mois
        </label>
        <Input
          id="mois-bulletin"
          type="month"
          uiSize="lg"
          aria-label="Mois du bulletin"
          value={mois}
          onChange={(evenement) => setMois(evenement.target.value)}
        />
        {CHAMPS.map(([cle, libelle]) => (
          <label key={cle} className="text-subtle" htmlFor={`bulletin-${cle}`}>
            {libelle}
            <Input
              id={`bulletin-${cle}`}
              inputMode="decimal"
              uiSize="lg"
              placeholder="1 000,50"
              value={montants[cle] ?? ""}
              onChange={(evenement) =>
                setMontants((actuels) => ({ ...actuels, [cle]: evenement.target.value }))
              }
            />
          </label>
        ))}
      </div>
      )}
      <Button className="mt-3 h-11" disabled={lecture !== "pret" || enCours || !mois || !montants.brut} onClick={enregistrer}>
        {enCours ? "Enregistrement…" : "Enregistrer le bulletin"}
      </Button>
      {erreur && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {erreur}
        </p>
      )}
    </section>
  );
}

/** Un champ vide vaut zéro (ces lignes peuvent être à zéro). Un texte
 * illisible est refusé. */
function lireEurosOuZero(saisie: string): number | string {
  const texte = saisie.replace(/[\s\u00a0\u202f]/g, "").replace(",", ".");
  if (texte === "" || texte === "0" || texte === "0.0" || texte === "0.00") return 0;
  const lu = lireEuros(saisie);
  if ("message" in lu) return lu.message;
  return lu.centimes;
}
