"use client";

import { useEffect, useId, useState } from "react";

import { BoutonLien } from "@/components/LienAction";
import { MessageAcces } from "@/components/MessageAcces";
import { TitreAcces } from "@/components/PageAcces";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { demanderReinitialisation, envoyerLienMagique } from "@/lib/auth-chauffeur";
import type { Cote } from "@/lib/cote-connexion";
import { prendreMessageConnexion } from "@/lib/message-connexion";
import { traduireExceptionAuth } from "@/lib/messages-auth";
import { sessionAExpire } from "@/lib/session";

type Mode = "mot_de_passe" | "lien" | "oubli";

/** Connexion par mot de passe, lien magique, ou e-mail de réinitialisation.
 * Les deux derniers atterrissent sur `/auth/lien`. */
export function FormulaireConnexion({
  titre,
  sousTitre,
  cote,
  onConnecte,
}: {
  titre: string;
  sousTitre: string;
  cote: Cote;
  onConnecte: (email: string, motDePasse: string) => Promise<void>;
}) {
  const idEmail = useId();
  const idMotDePasse = useId();
  const idErreur = useId();
  const [mode, setMode] = useState<Mode>("mot_de_passe");
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    const recherche = new URLSearchParams(window.location.search);
    const demande = recherche.get("mode");
    if (demande === "lien" || demande === "oubli") {
      // Le mode vient de l'adresse (« Mot de passe oublié », « nouveau lien »).
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMode(demande);
    }
    const refus = prendreMessageConnexion();
    if (refus) {
      setInfo(refus);
    } else if (sessionAExpire(window.location.search)) {
      setInfo("Votre session a expiré. Reconnectez-vous pour reprendre où vous en étiez.");
    }
  }, []);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnCours(true);
    setErreur(null);
    setInfo(null);
    try {
      const adresse = email.trim();
      if (mode === "lien") {
        await envoyerLienMagique(adresse, cote);
        setInfo("Si un compte existe pour cette adresse, le lien de connexion est envoyé.");
      } else if (mode === "oubli") {
        await demanderReinitialisation(adresse, cote);
        setInfo("Si un compte existe pour cette adresse, le lien de réinitialisation est envoyé.");
      } else {
        await onConnecte(adresse, motDePasse);
      }
    } catch (exception) {
      setErreur(traduireExceptionAuth(exception));
    } finally {
      setEnCours(false);
    }
  }

  function basculer(suivant: Mode) {
    setMode(suivant);
    setErreur(null);
    setInfo(null);
  }

  const decritErreur = erreur ? idErreur : undefined;

  return (
    <div>
      <TitreAcces grand>{titre}</TitreAcces>
      <p className="mt-2 text-base text-subtle">{sousTitre}</p>
      <form className="mt-8 space-y-4" onSubmit={soumettre}>
        <div className="space-y-1.5">
          <label htmlFor={idEmail} className="block text-sm font-medium text-ink">
            E-mail
          </label>
          <Input
            id={idEmail}
            name="email"
            type="email"
            autoComplete="email"
            uiSize="lg"
            value={email}
            onChange={(evenement) => setEmail(evenement.target.value)}
            placeholder="nom@exemple.fr"
            required
            disabled={enCours}
            aria-invalid={erreur ? true : undefined}
            aria-describedby={decritErreur}
          />
        </div>
        {mode === "mot_de_passe" && (
          <div className="space-y-1.5">
            <label htmlFor={idMotDePasse} className="block text-sm font-medium text-ink">
              Mot de passe
            </label>
            <Input
              id={idMotDePasse}
              name="password"
              type="password"
              autoComplete="current-password"
              uiSize="lg"
              value={motDePasse}
              onChange={(evenement) => setMotDePasse(evenement.target.value)}
              required
              disabled={enCours}
              aria-invalid={erreur ? true : undefined}
              aria-describedby={decritErreur}
            />
          </div>
        )}
        {erreur && (
          <MessageAcces ton="erreur" id={idErreur}>
            {erreur}
          </MessageAcces>
        )}
        {info && <MessageAcces ton="info">{info}</MessageAcces>}
        {/* Le bouton garde la hauteur du design (36 px) : le chauffeur le
            passe à 44 px par son habillage (`.chauffeur button`). */}
        <Button type="submit" disabled={enCours} className="w-full">
          {enCours
            ? "Envoi…"
            : mode === "lien"
              ? "Recevoir le lien"
              : mode === "oubli"
                ? "Recevoir le lien de réinitialisation"
                : "Se connecter"}
        </Button>
      </form>
      <div className="mt-6 flex flex-col items-start">
        {mode !== "lien" && <BoutonLien onClick={() => basculer("lien")}>Recevoir un lien de connexion</BoutonLien>}
        {mode !== "oubli" && <BoutonLien onClick={() => basculer("oubli")}>Mot de passe oublié</BoutonLien>}
        {mode !== "mot_de_passe" && (
          <BoutonLien onClick={() => basculer("mot_de_passe")}>Se connecter avec un mot de passe</BoutonLien>
        )}
      </div>
    </div>
  );
}
