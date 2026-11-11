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
  cheminApresChauffeur,
  lireFragmentAuth,
  ouvrirSessionDepuisJetons,
  pageInvitation,
  type FragmentAuth,
} from "@/lib/auth-lien";
import { coteDemandee, coteOuverte, type Cote } from "@/lib/cote-connexion";
import {
  MESSAGE_ESPACE_CHAUFFEUR,
  MESSAGE_ESPACE_GESTIONNAIRE,
  MESSAGE_SANS_LIEN,
} from "@/lib/messages-auth";
import {
  INDICATION_MOT_DE_PASSE,
  LONGUEUR_MIN_MOT_DE_PASSE,
  MESSAGE_LIEN_INCOMPLET,
  messageParametresAuth,
  traduireExceptionAuth,
} from "@/lib/messages-auth";

type Etape = "lecture" | "mot_de_passe" | "email_confirme" | "erreur";

/** Cible des liens Supabase : magique, réinitialisation, confirmation
 * d'adresse. Les jetons restent dans le fragment, jamais envoyés au serveur. */
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

  useEffect(() => {
    // Le fragment `#access_token` n'existe que dans le navigateur.
    /* eslint-disable react-hooks/set-state-in-effect */
    try {
      const recherche = new URLSearchParams(window.location.search);
      const demandee = coteDemandee(recherche.toString());
      setCote(demandee);
      const messageRecherche = messageParametresAuth(recherche);
      if (messageRecherche) throw new ErreurAuthChauffeur(messageRecherche);
      const code = recherche.get("code");
      if (code && !window.location.hash.includes("access_token=")) {
        throw new ErreurAuthChauffeur(MESSAGE_LIEN_INCOMPLET);
      }
      const recu = lireFragmentAuth(window.location.hash);
      if (recu.type === "invite" && pageInvitation(recu.accessToken) === "chauffeur") {
        window.location.replace(`/chauffeur/accepter-invitation${window.location.hash}`);
        return;
      }
      if (recu.type === "invite") {
        setFragment(recu);
        setPremiereConnexion(true);
        setEtape("mot_de_passe");
        return;
      }
      if (recu.type === "recovery") {
        setFragment(recu);
        setEtape("mot_de_passe");
        return;
      }
      const chemin = ouvrirSessionDepuisJetons(recu.accessToken, recu.refreshToken, demandee);
      if (recu.type === "email_change") {
        setDestination(chemin);
        setEtape("email_confirme");
        return;
      }
      router.replace(chemin);
    } catch (exception) {
      setErreur(traduireExceptionAuth(exception));
      setEtape("erreur");
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [router]);

  async function valider(evenement: React.FormEvent) {
    evenement.preventDefault();
    if (!fragment) return;
    setEnCours(true);
    setErreur(null);
    try {
      await definirMotDePasseAvecJeton(fragment.accessToken, motDePasse);
      const charge = decoderChargeUtileJwt(fragment.accessToken);
      const email = typeof charge.email === "string" ? charge.email : "";
      const decision = coteOuverte(charge.app_metadata, cote);
      if (decision === "chauffeur") {
        const session = await connexionParMotDePasse(email, motDePasse);
        router.replace(cheminApresChauffeur(session.accessToken, session));
      } else if (decision === "gestionnaire") {
        await connexionGestionnaire(email, motDePasse);
        router.replace("/");
      } else {
        throw new ErreurAuthChauffeur(
          decision === "interdit"
            ? cote === "gestionnaire"
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
