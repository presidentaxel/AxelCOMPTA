"use client";

// doc 06 §5 point 5 : le chauffeur sait qu'une charge de l'exercice n'est
// pas encore dans la banque. Il donne le montant. Le moteur ne décide pas
// à sa place quand provisionner.
import { useCallback, useEffect, useState } from "react";

import { EtatErreur } from "@/components/EtatChargement";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  enregistrerProvisionsCloture,
  lireProvisionsCloture,
} from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import {
  CHARGES_PROVISION,
  NATURE_PROVISION,
  libelleCharge,
} from "@/lib/libelles-chauffeur";
import { messageVisible } from "@/lib/messages";
import {
  lireEuros,
  listeAEnregistrer,
  listeSans,
  type LectureListe,
} from "@/lib/saisie-chauffeur";
import type { ProvisionClotureVue } from "@/lib/types";
import { Squelette } from "@/components/Squelette";

export function ProvisionsCloture({
  dossierId,
  onChange,
}: {
  dossierId: string;
  onChange: () => void;
}) {
  const [lecture, setLecture] = useState<LectureListe<ProvisionClotureVue>>({ statut: "en_cours" });
  const [nature, setNature] = useState<"cca" | "fnp">("fnp");
  const [compte, setCompte] = useState(CHARGES_PROVISION[0]?.compte ?? "628");
  const [montant, setMontant] = useState("");
  const [libelle, setLibelle] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  const charger = useCallback(() => {
    let annule = false;
    lireProvisionsCloture(dossierId)
      .then((lignes) => {
        if (!annule) setLecture({ statut: "pret", lignes });
      })
      .catch((exception: unknown) => {
        if (!annule) {
          setLecture({
            statut: "erreur",
            message: messageVisible(exception, "Impossible de charger ces charges."),
          });
        }
      });
    return () => {
      annule = true;
    };
  }, [dossierId]);

  useEffect(() => charger(), [charger]);

  function reessayer() {
    setErreur(null);
    setLecture({ statut: "en_cours" });
    charger();
  }

  async function envoyer(suivantes: ProvisionClotureVue[]): Promise<boolean> {
    setEnCours(true);
    setErreur(null);
    try {
      const enregistrees = await enregistrerProvisionsCloture(dossierId, suivantes);
      setLecture({ statut: "pret", lignes: enregistrees });
      onChange();
      return true;
    } catch (exception) {
      setErreur(
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "Échec de l'enregistrement.",
      );
      return false;
    } finally {
      setEnCours(false);
    }
  }

  async function ajouter() {
    const lu = lireEuros(montant);
    if ("message" in lu || libelle.trim() === "") {
      setErreur("message" in lu ? lu.message : "Indiquez ce que c'est, en quelques mots.");
      return;
    }
    const suivantes = listeAEnregistrer(lecture, {
      nature,
      compte_charge: compte,
      centimes: lu.centimes,
      libelle: libelle.trim(),
    });
    if (suivantes === null) {
      return;
    }
    const ok = await envoyer(suivantes);
    if (!ok) {
      return;
    }
    setMontant("");
    setLibelle("");
  }

  async function retirer(index: number) {
    const suivantes = listeSans(lecture, index);
    if (suivantes === null) {
      return;
    }
    await envoyer(suivantes);
  }

  const lignes = lecture.statut === "pret" ? lecture.lignes : [];

  return (
    <div className="mt-4 rounded-md border border-border bg-canvas p-3">
      <p className="text-sm text-ink">Une charge de cet exercice n&apos;est pas encore passée ?</p>
      <p className="mt-1 text-sm text-subtle">
        Donnez votre estimation. Elle sera prise dans la clôture. Rien n&apos;est deviné.
      </p>
      {lecture.statut === "en_cours" && <Squelette className="mt-3 h-11 w-full" />}
      {lecture.statut === "erreur" && (
        <EtatErreur message={lecture.message} onReessayer={reessayer} />
      )}
      {lecture.statut === "pret" && (
        <>
          {lignes.length > 0 && (
            <ul className="mt-3 space-y-2 text-sm text-ink">
              {lignes.map((ligne, index) => (
                <li
                  key={`${ligne.nature}-${ligne.compte_charge}-${ligne.libelle}-${index}`}
                  className="flex items-center justify-between gap-3"
                >
                  <span>
                    {NATURE_PROVISION[ligne.nature]} — {ligne.libelle} (
                    {libelleCharge(ligne.compte_charge)})
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="tabular-nums">{formatMontant(ligne.centimes)}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-11"
                      disabled={enCours}
                      onClick={() => void retirer(index)}
                    >
                      Retirer
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex flex-col gap-2">
            <label className="text-sm text-subtle" htmlFor="nature-provision">
              De quoi s&apos;agit-il ?
            </label>
            <select
              id="nature-provision"
              className="h-11 rounded-md border border-border bg-canvas px-3 text-base"
              value={nature}
              onChange={(evenement) => setNature(evenement.target.value === "cca" ? "cca" : "fnp")}
            >
              <option value="fnp">{NATURE_PROVISION.fnp}</option>
              <option value="cca">{NATURE_PROVISION.cca}</option>
            </select>
            <label className="text-sm text-subtle" htmlFor="charge-provision">
              Quelle charge ?
            </label>
            <select
              id="charge-provision"
              className="h-11 rounded-md border border-border bg-canvas px-3 text-base"
              value={compte}
              onChange={(evenement) => setCompte(evenement.target.value)}
            >
              {CHARGES_PROVISION.map((charge) => (
                <option key={charge.compte} value={charge.compte}>
                  {charge.libelle}
                </option>
              ))}
            </select>
            <label className="text-sm text-subtle" htmlFor="montant-provision">
              Montant
            </label>
            <input
              id="montant-provision"
              className="h-11 rounded-md border border-border px-3 text-base"
              inputMode="decimal"
              placeholder="1 000,50"
              value={montant}
              onChange={(evenement) => setMontant(evenement.target.value)}
            />
            <label className="text-sm text-subtle" htmlFor="libelle-provision">
              En quelques mots
            </label>
            <input
              id="libelle-provision"
              className="h-11 rounded-md border border-border px-3 text-base"
              placeholder="Assurance de janvier, pas encore débitée"
              value={libelle}
              onChange={(evenement) => setLibelle(evenement.target.value)}
            />
            <Button type="button" variant="secondary" className="h-11" disabled={enCours} onClick={ajouter}>
              Ajouter
            </Button>
          </div>
        </>
      )}
      {erreur && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {erreur}
        </p>
      )}
    </div>
  );
}
