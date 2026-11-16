"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { lireListe, totalParts, type Associe, type ChampImport } from "@/lib/fiches-import";

import type { Enregistrer } from "./ChampAuto";

const VIDE: Associe = { prenom: "", nom: "", fonction: "associe", pourcentage: "" };

/** AXE-946 : les associés en lignes (prénom, nom, fonction, part du capital).
 * Préremplis par les dirigeants lus au RNE ; enregistrés ensemble. */
export function AssociesImport({
  champ,
  modifiable,
  enregistrer,
}: {
  champ: ChampImport;
  modifiable: boolean;
  enregistrer: Enregistrer;
}) {
  const depart = lireListe<Associe>(champ.valeur);
  const [lignes, setLignes] = useState<Associe[]>(depart.length > 0 ? depart : [VIDE]);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const ancienTexte = champ.valeur && depart.length === 0 ? champ.valeur : null;
  const remplies = lignes.filter((l) => l.nom.trim() || l.prenom.trim() || l.pourcentage.trim());
  const modifiees = JSON.stringify(remplies) !== JSON.stringify(depart);
  const total = totalParts(remplies);

  function changer(index: number, cle: keyof Associe, valeur: string) {
    setLignes((avant) => avant.map((l, i) => (i === index ? { ...l, [cle]: valeur } : l)));
  }

  async function sauver() {
    setEnvoi(true);
    setErreur(null);
    try {
      await enregistrer({ associes: remplies.length ? JSON.stringify(remplies) : "" });
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <fieldset className="space-y-3 sm:col-span-2">
      <legend className="flex w-full items-center justify-between text-sm font-medium text-ink">
        Associés
        <span className={`text-xs font-normal ${total > 0 && total !== 100 ? "text-warning" : "text-muted"}`}>
          Total : {total.toLocaleString("fr-FR")} % sur 100 %
        </span>
      </legend>
      {ancienTexte && (
        <p className="rounded-md bg-canvas-app p-2 text-xs text-subtle">Saisie précédente : {ancienTexte}</p>
      )}
      <ul className="space-y-2">
        {lignes.map((ligne, index) => (
          <li key={index} className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_1fr_11rem_6rem_auto]">
            <Input
              aria-label={`Prénom de l'associé ${index + 1}`}
              placeholder="Prénom"
              value={ligne.prenom}
              disabled={!modifiable}
              onChange={(e) => changer(index, "prenom", e.target.value)}
            />
            <Input
              aria-label={`Nom de l'associé ${index + 1}`}
              placeholder="Nom"
              value={ligne.nom}
              disabled={!modifiable}
              onChange={(e) => changer(index, "nom", e.target.value)}
            />
            <Select
              aria-label={`Fonction de l'associé ${index + 1}`}
              value={ligne.fonction}
              disabled={!modifiable}
              onValueChange={(v) => changer(index, "fonction", v)}
              options={champ.choix.map((c) => ({ value: c.cle, label: c.libelle }))}
            />
            <div className="relative">
              <Input
                aria-label={`Part du capital de l'associé ${index + 1}`}
                inputMode="decimal"
                placeholder="%"
                className="pr-7"
                value={ligne.pourcentage}
                disabled={!modifiable}
                onChange={(e) => changer(index, "pourcentage", e.target.value)}
              />
              <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm text-muted">%</span>
            </div>
            {modifiable && (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-label={`Retirer l'associé ${index + 1}`}
                className="self-center"
                onClick={() => setLignes((avant) => (avant.length > 1 ? avant.filter((_, i) => i !== index) : [VIDE]))}
              >
                <Trash2 className="size-4" aria-hidden />
              </Button>
            )}
          </li>
        ))}
      </ul>
      {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
      {modifiable && (
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={() => setLignes((avant) => [...avant, VIDE])}>
            <Plus className="size-4" aria-hidden /> Ajouter un associé
          </Button>
          {modifiees && (
            <Button type="button" size="sm" disabled={envoi} onClick={sauver}>
              {envoi ? "Enregistrement…" : "Enregistrer les associés"}
            </Button>
          )}
        </div>
      )}
    </fieldset>
  );
}
