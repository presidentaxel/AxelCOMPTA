"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { MessageAcces } from "@/components/MessageAcces";
import { TitreAcces } from "@/components/PageAcces";
import { SuitesAuth } from "@/components/SuitesAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  connexionParMotDePasse,
  decoderChargeUtileJwt,
  definirMotDePasseAvecJeton,
  ErreurAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { connexionGestionnaire } from "@/lib/auth-gestionnaire";
import {
  codeNormalise,
  facteurVerifie,
  lireFacteurs,
  verifierCode,
  type Facteur,
} from "@/lib/mfa";
import {
  cheminApresChauffeur,
  lireLienCourant,
  ouvrirSessionDepuisJetons,
  pageInvitation,
  type FragmentAuth,
} from "@/lib/auth-lien";
import { coteOuverte, type Cote } from "@/lib/cote-connexion";
import {
  INDICATION_MOT_DE_PASSE,
  LONGUEUR_MIN_MOT_DE_PASSE,
  MESSAGE_CODE_REQUIS,
  MESSAGE_ESPACE_CHAUFFEUR,
  MESSAGE_ESPACE_GESTIONNAIRE,
  MESSAGE_SANS_LIEN,
  traduireExceptionAuth,
} from "@/lib/messages-auth";

type Etape = "lecture" | "mot_de_passe" | "email_confirme" | "erreur";

/** Cible des liens Supabase : magique, réinitialisation, confirmation
 * d'adresse. Le courriel pose `token_hash` dans l'adresse ; un fragment
 * `#access_token` reste accepté pour un courriel déjà envoyé. */
export default function LienAuthPage() {
  const router = useRouter();
  const idMotDePasse = useId();
  const [etape, setEtape] = useState<Etape>("lecture");
  const [fragment, setFragment] = useState<FragmentAuth | null>(null);
  const [destination, setDestination] = useState("/");
  const [motDePasse, setMotDePasse] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [premiereConnexion, setPremiereConnexion] = useState(false);
  const [cote, setCote] = useState<Cote | null>(null);
  // AXE-961 : avec la double authentification, Supabase exige le code avant
  // de changer le mot de passe (session `aal2`).
  const [facteur, setFacteur] = useState<Facteur | null>(null);
  const [code, setCode] = useState("");

  useEffect(() => {
    let ignore = false;
    // Le fragment `#access_token` n'existe que dans le navigateur.
    void (async () => {
      try {
        const recuLien = await lireLienCourant();
        if (ignore) return;
        const recu = recuLien.fragment;
        const demandee = recuLien.cote;
        setCote(demandee);
        if (recu.type === "invite" && pageInvitation(recu.accessToken) === "chauffeur") {
          window.location.replace(
            `/chauffeur/accepter-invitation${window.location.search}${window.location.hash}`,
          );
          return;
        }
        if (recu.type === "invite") {
          setFragment(recu);
          setPremiereConnexion(true);
          setEtape("mot_de_passe");
          return;
        }
        if (recu.type === "recovery") {
          const verifie = await lireFacteurs(recu.accessToken)
            .then(facteurVerifie)
            .catch(() => null);
          if (ignore) return;
          setFacteur(verifie);
          setFragment(recu);
          setEtape("mot_de_passe");
          return;
        }
        const chargeLien = decoderChargeUtileJwt(recu.accessToken);
        const compatible =
          demandee !== null && coteOuverte(chargeLien.app_metadata, demandee) !== "interdit";
        const demandeeOuvrir = compatible ? demandee : null;
        const chemin = ouvrirSessionDepuisJetons(
          recu.accessToken,
          recu.refreshToken,
          demandeeOuvrir,
        );
        if (recu.type === "email_change") {
          setDestination(chemin);
          setEtape("email_confirme");
          return;
        }
        router.replace(chemin);
      } catch (exception) {
        if (ignore) return;
        setErreur(traduireExceptionAuth(exception));
        setEtape("erreur");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [router]);

  async function valider(evenement: React.FormEvent) {
    evenement.preventDefault();
    if (!fragment) return;
    setEnCours(true);
    setErreur(null);
    try {
      const jeton = facteur
        ? await jetonAvecCode(fragment.accessToken, facteur, code)
        : fragment.accessToken;
      await definirMotDePasseAvecJeton(jeton, motDePasse);
      const charge = decoderChargeUtileJwt(jeton);
      const email = typeof charge.email === "string" ? charge.email : "";
      const demandee = cote && coteOuverte(charge.app_metadata, cote) !== "interdit" ? cote : null;
      const decision = coteOuverte(charge.app_metadata, demandee);
      if (decision === "chauffeur") {
        const session = await connexionParMotDePasse(email, motDePasse);
        router.replace(cheminApresChauffeur(session.accessToken, session));
      } else if (decision === "gestionnaire") {
        await connexionGestionnaire(email, motDePasse);
        router.replace("/");
      } else {
        throw new ErreurAuthChauffeur(
          decision === "interdit"
            ? demandee === "gestionnaire"
              ? MESSAGE_ESPACE_CHAUFFEUR
              : MESSAGE_ESPACE_GESTIONNAIRE
            : MESSAGE_SANS_LIEN,
        );
      }
    } catch (exception) {
      setErreur(traduireExceptionAuth(exception));
    } finally {
      setEnCours(false);
    }
  }

  if (etape === "lecture") {
    return <MessageAcces ton="attente">Vérification du lien…</MessageAcces>;
  }

  if (etape === "erreur") {
    return (
      <div>
        <TitreAcces>Lien inutilisable</TitreAcces>
        <MessageAcces ton="erreur" className="mt-4">
          {erreur}
        </MessageAcces>
        <SuitesAuth />
      </div>
    );
  }

  if (etape === "email_confirme") {
    return (
      <div>
        <TitreAcces>Adresse confirmée</TitreAcces>
        <MessageAcces ton="succes" className="mt-4">
          La nouvelle adresse est active.
        </MessageAcces>
        <Button type="button" className="mt-8 w-full" onClick={() => router.replace(destination)}>
          Continuer
        </Button>
      </div>
    );
  }

  const idRegle = `${idMotDePasse}-regle`;
  const idErreur = `${idMotDePasse}-erreur`;
  return (
    <div>
      <TitreAcces>{premiereConnexion ? "Bienvenue" : "Nouveau mot de passe"}</TitreAcces>
      <p className="mt-2 text-base text-subtle">
        Choisissez un mot de passe pour vos prochaines connexions.
      </p>
      <form className="mt-8 space-y-4" onSubmit={valider}>
        <div className="space-y-1.5">
          <label htmlFor={idMotDePasse} className="block text-sm font-medium text-ink">
            Nouveau mot de passe
          </label>
          <p id={idRegle} className="text-sm text-subtle">
            {INDICATION_MOT_DE_PASSE}
          </p>
          <Input
            id={idMotDePasse}
            name="new-password"
            type="password"
            autoComplete="new-password"
            uiSize="lg"
            value={motDePasse}
            onChange={(evenement) => setMotDePasse(evenement.target.value)}
            required
            minLength={LONGUEUR_MIN_MOT_DE_PASSE}
            disabled={enCours}
            aria-describedby={erreur ? `${idRegle} ${idErreur}` : idRegle}
            aria-invalid={erreur ? true : undefined}
          />
        </div>
        {facteur && (
          <div className="space-y-1.5">
            <label htmlFor={`${idMotDePasse}-code`} className="block text-sm font-medium text-ink">
              Code de double authentification
            </label>
            <p className="text-sm text-subtle">
              Les 6 chiffres affichés dans votre application d&apos;authentification.
            </p>
            <Input
              id={`${idMotDePasse}-code`}
              name="one-time-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              uiSize="lg"
              value={code}
              onChange={(evenement) => setCode(evenement.target.value)}
              required
              disabled={enCours}
            />
          </div>
        )}
        {erreur && (
          <MessageAcces ton="erreur" id={idErreur}>
            {erreur}
          </MessageAcces>
        )}
        <Button type="submit" disabled={enCours} className="w-full">
          {enCours ? "Enregistrement…" : "Valider"}
        </Button>
      </form>
    </div>
  );
}

/** AXE-961 : le code de l'application donne une session `aal2`, seule
 * autorisée à changer le mot de passe d'un compte en double authentification. */
async function jetonAvecCode(accessToken: string, facteur: Facteur, saisie: string): Promise<string> {
  const code = codeNormalise(saisie);
  if (!code) throw new ErreurAuthChauffeur(MESSAGE_CODE_REQUIS);
  try {
    return (await verifierCode(accessToken, facteur.id, code)).accessToken;
  } catch (exception) {
    throw new ErreurAuthChauffeur(
      exception instanceof Error ? exception.message : MESSAGE_CODE_REQUIS,
    );
  }
}
