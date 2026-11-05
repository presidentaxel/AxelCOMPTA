"use client";

import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { INDICATION_MOT_DE_PASSE, LONGUEUR_MIN_MOT_DE_PASSE, traduireExceptionAuth } from "@/lib/messages-auth";

/** Changement de mot de passe (session déjà ouverte) et demande de
 * changement d'adresse. L'adresse ne bouge qu'après le clic sur le lien
 * envoyé par Supabase. */
export function FormulaireCompte({
  email,
  onMotDePasse,
  onEmail,
}: {
  email: string;
  onMotDePasse: (motDePasse: string) => Promise<void>;
  onEmail: (email: string) => Promise<void>;
}) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="mb-1 text-xl font-bold text-ink">Compte</h1>
        {email && <p className="text-sm text-subtle">Adresse actuelle : {email}</p>}
      </div>
      <Formulaire
        titre="Nouveau mot de passe"
        type="password"
        autoComplete="new-password"
        indication={INDICATION_MOT_DE_PASSE}
        minLength={LONGUEUR_MIN_MOT_DE_PASSE}
        libelle="Enregistrer le mot de passe"
        onValider={onMotDePasse}
        succes="Mot de passe mis à jour."
      />
      <Formulaire
        titre="Nouvelle adresse e-mail"
        type="email"
        autoComplete="email"
        placeholder="nouvelle@adresse.fr"
        libelle="Recevoir le lien de confirmation"
        onValider={onEmail}
        succes="Un lien de confirmation a été envoyé à cette adresse. L'ancienne reste active jusqu'au clic."
      />
    </div>
  );
}

function Formulaire({
  titre,
  type,
  autoComplete,
  placeholder,
  indication,
  libelle,
  minLength,
  onValider,
  succes,
}: {
  titre: string;
  type: "password" | "email";
  autoComplete: "new-password" | "email";
  placeholder?: string;
  indication?: string;
  libelle: string;
  minLength?: number;
  onValider: (valeur: string) => Promise<void>;
  succes: string;
}) {
  const id = useId();
  const idRegle = `${id}-regle`;
  const [valeur, setValeur] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnCours(true);
    setErreur(null);
    setInfo(null);
    try {
      // L'e-mail se nettoie ; le mot de passe est gardé tel quel (les espaces
      // peuvent en faire partie), comme à la connexion.
      await onValider(type === "email" ? valeur.trim() : valeur);
      setValeur("");
      setInfo(succes);
    } catch (exception) {
      setErreur(traduireExceptionAuth(exception));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <form className="space-y-3" onSubmit={soumettre}>
      <div className="space-y-1">
        <label htmlFor={id} className="block text-sm font-semibold text-ink">
          {titre}
        </label>
        {indication && (
          <p id={idRegle} className="text-sm text-subtle">
            {indication}
          </p>
        )}
        <Input
          id={id}
          name={type === "email" ? "email" : "new-password"}
          type={type}
          autoComplete={autoComplete}
          uiSize="lg"
          value={valeur}
          onChange={(evenement) => setValeur(evenement.target.value)}
          placeholder={placeholder}
          required
          minLength={minLength}
          disabled={enCours}
          aria-describedby={indication ? idRegle : undefined}
          aria-invalid={erreur ? true : undefined}
        />
      </div>
      {erreur && (
        <p role="alert" className="text-sm text-danger">
          {erreur}
        </p>
      )}
      {info && (
        <p role="status" className="text-sm text-subtle">
          {info}
        </p>
      )}
      <Button type="submit" disabled={enCours}>
        {enCours ? "Envoi…" : libelle}
      </Button>
    </form>
  );
}
