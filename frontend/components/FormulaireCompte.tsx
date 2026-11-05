"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MOT_DE_PASSE_MIN, motDePasseAcceptable } from "@/lib/messages-auth";

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
        placeholder={`Au moins ${MOT_DE_PASSE_MIN} caractères`}
        libelle="Enregistrer le mot de passe"
        minLength={MOT_DE_PASSE_MIN}
        autoComplete="new-password"
        onValider={onMotDePasse}
        succes="Mot de passe mis à jour."
      />
      <Formulaire
        titre="Nouvelle adresse e-mail"
        type="email"
        placeholder="nouvelle@adresse.fr"
        libelle="Recevoir le lien de confirmation"
        autoComplete="email"
        onValider={onEmail}
        succes="Un lien de confirmation a été envoyé à cette adresse. L'ancienne reste active jusqu'au clic."
      />
    </div>
  );
}

function Formulaire({
  titre,
  type,
  placeholder,
  libelle,
  minLength,
  autoComplete,
  onValider,
  succes,
}: {
  titre: string;
  type: "password" | "email";
  placeholder: string;
  libelle: string;
  minLength?: number;
  autoComplete: string;
  onValider: (valeur: string) => Promise<void>;
  succes: string;
}) {
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
      const saisie = type === "email" ? valeur.trim() : valeur;
      if (type === "password") {
        const refus = motDePasseAcceptable(saisie);
        if (refus) {
          setErreur(refus);
          return;
        }
      }
      await onValider(saisie);
      setValeur("");
      setInfo(succes);
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Échec de l'enregistrement.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <form className="space-y-3" onSubmit={soumettre}>
      <h2 className="text-sm font-semibold text-ink">
        <label htmlFor={`compte-${type}`}>{titre}</label>
      </h2>
      {type === "password" && (
        <p className="text-sm text-subtle">Au moins {MOT_DE_PASSE_MIN} caractères.</p>
      )}
      <Input
        id={`compte-${type}`}
        type={type}
        uiSize="lg"
        autoComplete={autoComplete}
        value={valeur}
        onChange={(evenement) => setValeur(evenement.target.value)}
        placeholder={placeholder}
        required
        minLength={minLength}
        disabled={enCours}
      />
      {erreur && (
        <p role="alert" className="text-sm text-danger">
          {erreur}
        </p>
      )}
      {info && <p className="text-sm text-subtle">{info}</p>}
      <Button type="submit" disabled={enCours}>
        {enCours ? "Envoi…" : libelle}
      </Button>
    </form>
  );
}
