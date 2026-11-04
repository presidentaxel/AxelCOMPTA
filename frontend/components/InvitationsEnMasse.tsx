"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { inviterEnMasse, type InvitationsMasse } from "@/lib/auth-gestionnaire";
import type { DossierAgregat } from "@/lib/types";

const MAX_LIGNES = 500;

const LIBELLES: Record<string, string> = {
  invité: "Invitation envoyée",
  deja_invite: "Déjà invité",
  dossier_inconnu: "Dossier inconnu",
  email_invalide: "E-mail invalide",
  doublon_dans_le_lot: "Doublon dans le fichier",
  erreur: "Échec d'envoi",
};

const MODELE = "Nom de l'entreprise, email@exemple.fr";

/** Lit « dossier_id,email » (ou séparé par point-virgule / tabulation), une
 * paire par ligne ; ignore les lignes vides et un éventuel en-tête. */
function lireLignes(texte: string): { dossier_id: string; email: string }[] {
  return texte
    .split(/\r?\n/)
    .map((ligne) => ligne.split(/[,;\t]/).map((partie) => partie.trim()))
    .filter(([dossier, email]) => dossier && email && dossier.toLowerCase() !== "dossier_id")
    .map(([dossier_id, email]) => ({ dossier_id, email }));
}

/** Dit pourquoi le collage n'a donné aucune invitation, pour l'afficher au clic. */
function motifIllisible(texte: string): string {
  const brutes = texte
    .split(/\r?\n/)
    .map((ligne) => ligne.trim())
    .filter((ligne) => ligne.length > 0)
    .filter((ligne) => ligne.split(/[,;\t]/)[0]?.trim().toLowerCase() !== "dossier_id");
  const premiere = brutes[0]?.split(/[,;\t]/).map((partie) => partie.trim()).filter(Boolean) ?? [];
  if (premiere.length < 2 && premiere[0]?.includes("@")) {
    return `Il manque le nom de l'entreprise. Écrivez « ${MODELE} ».`;
  }
  if (premiere.length < 2) {
    return `Il manque l'e-mail. Écrivez « ${MODELE} ».`;
  }
  return `Aucune invitation reconnue. Écrivez « ${MODELE} ».`;
}

/** doc 19 §3.1 : invitation en masse depuis une base clients. Un fichier ou un
 * collage, un aperçu du nombre de lignes, puis un résultat ligne par ligne :
 * les lignes en échec n'empêchent pas les autres. */
export function InvitationsEnMasse({
  dossiers,
  desactive = false,
  onTermine,
}: {
  dossiers: DossierAgregat[];
  desactive?: boolean;
  onTermine: () => void;
}) {
  const [texte, setTexte] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [resultat, setResultat] = useState<InvitationsMasse | null>(null);

  const lignes = lireLignes(texte).map((ligne) => {
    const connu = dossiers.some((dossier) => dossier.dossier_id === ligne.dossier_id);
    if (connu) return ligne;
    const parNom = dossiers.find(
      (dossier) => dossier.nom.trim().toLowerCase() === ligne.dossier_id.toLowerCase(),
    );
    return parNom ? { dossier_id: parNom.dossier_id, email: ligne.email } : ligne;
  });
  const troploin = lignes.length > MAX_LIGNES;

  async function charger(evenement: React.ChangeEvent<HTMLInputElement>) {
    const fichier = evenement.target.files?.[0];
    if (fichier) setTexte(await fichier.text());
  }

  async function envoyer() {
    if (lignes.length === 0) {
      setResultat(null);
      setErreur(motifIllisible(texte));
      return;
    }
    setEnCours(true);
    setErreur(null);
    try {
      setResultat(await inviterEnMasse(lignes));
      onTermine();
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Échec de l'envoi.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section>
      <p className="mb-3 text-sm text-subtle">
        Une ligne par entreprise : nom ou identifiant, e-mail. {MAX_LIGNES} lignes au plus.
      </p>
      <label
        className={`mb-3 inline-flex h-9 items-center rounded-md border border-border-strong bg-canvas px-4 text-sm font-semibold text-ink ${
          desactive ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:bg-canvas-app"
        }`}
      >
        Choisir un fichier
        <input
          type="file"
          accept=".csv,.txt"
          onChange={charger}
          disabled={desactive || enCours}
          className="sr-only"
        />
      </label>
      <textarea
        value={texte}
        onChange={(evenement) => {
          setTexte(evenement.target.value);
          setErreur(null);
        }}
        rows={5}
        placeholder="Nom de l'entreprise, email@exemple.fr"
        disabled={desactive || enCours}
        className="w-full rounded-md border border-border px-3 py-2 font-mono text-xs"
      />
      <div className="mt-2 flex items-center gap-3">
        <Button
          type="button"
          variant="secondary"
          onClick={envoyer}
          disabled={desactive || enCours || texte.trim().length === 0 || troploin}
        >
          {enCours ? "Envoi…" : lignes.length > 0 ? `Inviter ${lignes.length}` : "Inviter"}
        </Button>
        {troploin && <span className="text-sm text-danger">Trop de lignes ({lignes.length}).</span>}
        {erreur && <span className="text-sm text-danger">{erreur}</span>}
      </div>
      {resultat && (
        <div className="mt-4">
          <p className="mb-2 text-sm font-semibold text-ink">
            {resultat.nb_invitees} invitation(s) envoyée(s) sur {resultat.lignes.length} ligne(s).
          </p>
          <table className="w-full text-left text-xs">
            <tbody>
              {resultat.lignes.map((ligne, rang) => (
                <tr key={rang} className="border-t border-border">
                  <td className="py-1 pr-3 font-mono">{ligne.dossier_id}</td>
                  <td className="py-1 pr-3">{ligne.email}</td>
                  <td
                    className={`py-1 ${ligne.resultat === "invité" ? "text-amount-positive" : "text-subtle"}`}
                  >
                    {LIBELLES[ligne.resultat] ?? ligne.resultat}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
