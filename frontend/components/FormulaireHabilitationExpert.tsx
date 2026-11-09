"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { habiliterExpert, listerDossiers } from "@/lib/auth-gestionnaire";
import type { DossierAgregat } from "@/lib/types";

const VIDE = { email: "", nom: "", cabinet: "", numero_ordre: "", lettre_mission: "", date_lettre: "" };

/** AXE-800 : un admin déclare l'expert-comptable du portefeuille et les
 * dossiers couverts par sa lettre de mission. Déclaratif et tracé : une
 * nouvelle déclaration remplace la précédente, rien ne s'efface. */
export function FormulaireHabilitationExpert({ actif }: { actif: boolean }) {
  const [champs, setChamps] = useState(VIDE);
  const [dossiers, setDossiers] = useState<DossierAgregat[]>([]);
  const [couverts, setCouverts] = useState<string[]>([]);
  const [message, setMessage] = useState<{ texte: string; erreur: boolean } | null>(null);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    listerDossiers()
      .then(setDossiers)
      .catch(() => setDossiers([]));
  }, []);

  function ecrire(nom: keyof typeof VIDE, valeur: string) {
    setChamps((actuel) => ({ ...actuel, [nom]: valeur }));
  }

  async function envoyer(evenement: React.FormEvent) {
    evenement.preventDefault();
    if (couverts.length === 0) {
      setMessage({ texte: "Cochez au moins un dossier de la lettre de mission.", erreur: true });
      return;
    }
    setEnvoi(true);
    setMessage(null);
    try {
      const faite = await habiliterExpert({ ...champs, dossiers: couverts });
      setMessage({
        texte: `${faite.nom} est habilité(e) sur ${faite.dossiers.length} dossier(s). Il ou elle acceptera l'engagement de responsabilité à sa première visite du mode expert.`,
        erreur: false,
      });
      setChamps(VIDE);
      setCouverts([]);
    } catch (exception) {
      setMessage({
        texte: exception instanceof Error ? exception.message : "Échec de l'habilitation.",
        erreur: true,
      });
    } finally {
      setEnvoi(false);
    }
  }

  const libelles: [keyof typeof VIDE, string, string][] = [
    ["email", "E-mail", "email"],
    ["nom", "Nom et prénom", "text"],
    ["cabinet", "Cabinet", "text"],
    ["numero_ordre", "N° d'inscription à l'Ordre", "text"],
    ["lettre_mission", "Référence de la lettre de mission", "text"],
    ["date_lettre", "Date de la lettre de mission", "date"],
  ];

  return (
    <form onSubmit={envoyer} className="mt-10 max-w-xl space-y-3" aria-labelledby="titre-habilitation">
      <p id="titre-habilitation" className="text-sm font-medium text-ink">
        Habiliter un expert-comptable
      </p>
      <p className="text-sm text-subtle">
        Seul l&apos;expert-comptable habilité voit le détail des dossiers et y écrit, sous sa
        responsabilité. Le portefeuille garde les agrégats.
      </p>
      {libelles.map(([nom, libelle, type]) => (
        <label key={nom} className="block text-sm text-ink">
          {libelle}
          <Input
            type={type}
            required
            value={champs[nom]}
            onChange={(e) => ecrire(nom, e.target.value)}
            disabled={!actif || envoi}
            className="mt-1"
          />
        </label>
      ))}
      <fieldset className="text-sm text-ink">
        <legend>Dossiers couverts</legend>
        <ul className="mt-1 max-h-48 space-y-1 overflow-y-auto">
          {dossiers.map((dossier) => (
            <li key={dossier.dossier_id}>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  disabled={!actif || envoi}
                  checked={couverts.includes(dossier.dossier_id)}
                  onChange={(e) =>
                    setCouverts((actuel) =>
                      e.target.checked
                        ? [...actuel, dossier.dossier_id]
                        : actuel.filter((id) => id !== dossier.dossier_id),
                    )
                  }
                />
                {dossier.nom}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      {message && (
        <p role="status" className={`text-sm ${message.erreur ? "text-danger" : "text-ink"}`}>
          {message.texte}
        </p>
      )}
      <Button type="submit" disabled={!actif || envoi}>
        {envoi ? "Enregistrement…" : "Habiliter"}
      </Button>
    </form>
  );
}
