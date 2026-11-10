"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { SaisieCode } from "@/components/SaisieCode";
import { Button } from "@/components/ui/button";
import {
  obtenirSession,
  remplacerJetonsChauffeur,
} from "@/lib/auth-chauffeur";
import {
  obtenirSessionGestionnaire,
  remplacerJetonsGestionnaire,
} from "@/lib/auth-gestionnaire";
import {
  codeNormalise,
  enroler,
  facteurVerifie,
  lireFacteurs,
  verifierCode,
  type Enrolement,
} from "@/lib/mfa";
import { cheminDeRetour } from "@/lib/session";

type Etape =
  | { statut: "chargement" }
  | { statut: "erreur"; message: string }
  | { statut: "code"; facteurId: string }
  | { statut: "enrolement"; enrolement: Enrolement };

/** AXE-812 : double authentification. Le gestionnaire et le compte de test
 * s'arrêtent ici. Sans facteur, enrôlement (QR) ; avec, saisie du code.
 * Le code vérifié donne une session `aal2`. */
export default function DoubleAuthentificationPage() {
  const router = useRouter();
  const [etape, setEtape] = useState<Etape>({ statut: "chargement" });
  const [saisie, setSaisie] = useState("");
  const [refus, setRefus] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  const preparer = useCallback(async () => {
    setEtape({ statut: "chargement" });
    const cote = new URLSearchParams(window.location.search).get("cote");
    const session = cote === "chauffeur" ? obtenirSession() : obtenirSessionGestionnaire();
    if (!session) {
      router.replace(cote === "chauffeur" ? "/chauffeur/login" : "/connexion");
      return;
    }
    try {
      const facteurs = await lireFacteurs(session.accessToken);
      const verifie = facteurVerifie(facteurs);
      setEtape(
        verifie
          ? { statut: "code", facteurId: verifie.id }
          : { statut: "enrolement", enrolement: await enroler(session.accessToken, facteurs) },
      );
    } catch (exception) {
      setEtape({
        statut: "erreur",
        message: exception instanceof Error ? exception.message : "Erreur inattendue.",
      });
    }
  }, [router]);

  useEffect(() => {
    // Une seule fois : relancer referait un QR à chaque rendu.
    // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
    void preparer();
  }, []);

  async function valider(evenement: React.FormEvent) {
    evenement.preventDefault();
    const code = codeNormalise(saisie);
    const cote = new URLSearchParams(window.location.search).get("cote");
    const session = cote === "chauffeur" ? obtenirSession() : obtenirSessionGestionnaire();
    if (!code || !session || (etape.statut !== "code" && etape.statut !== "enrolement")) {
      setRefus("Saisissez les 6 chiffres affichés par votre application.");
      return;
    }
    const facteurId = etape.statut === "code" ? etape.facteurId : etape.enrolement.facteurId;
    setEnvoi(true);
    setRefus(null);
    try {
      const jetons = await verifierCode(session.accessToken, facteurId, code);
      if (cote === "chauffeur") {
        remplacerJetonsChauffeur(jetons.accessToken, jetons.refreshToken);
      } else {
        remplacerJetonsGestionnaire(jetons.accessToken, jetons.refreshToken);
      }
      const retour = cheminDeRetour(
        window.location.search,
        cote === "chauffeur" ? "/chauffeur/test" : "/",
      );
      router.replace(retour === "/securite" || retour.startsWith("/securite?") ? "/" : retour);
    } catch (exception) {
      setRefus(exception instanceof Error ? exception.message : "Code refusé.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <section aria-labelledby="titre-double-auth">
      <h1 id="titre-double-auth" className="text-xl font-bold text-ink">
        Double authentification
      </h1>
      {etape.statut === "chargement" && (
        <div className="mt-6 space-y-3" aria-hidden>
          <Squelette className="h-52 w-52" />
          <Squelette className="h-9 w-full" />
        </div>
      )}
      {etape.statut === "erreur" && (
        <Etat type="erreur" message={etape.message} onReessayer={() => void preparer()} />
      )}
      {etape.statut === "enrolement" && (
        <div className="mt-4 space-y-4 text-sm text-ink">
          <p>
            Votre rôle demande un code en plus du mot de passe. Scannez ce QR code avec une
            application d&apos;authentification (Google Authenticator, 1Password, Authy…), puis
            saisissez le code qu&apos;elle affiche.
          </p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={etape.enrolement.qrCode}
            alt="QR code à scanner avec votre application d'authentification"
            className="h-52 w-52 rounded-md border border-border bg-white p-2"
          />
          <p className="text-subtle">
            Sans appareil photo, saisissez cette clé :{" "}
            <code className="break-all font-mono text-ink">{etape.enrolement.secret}</code>
          </p>
        </div>
      )}
      {etape.statut === "code" && (
        <p className="mt-4 text-sm text-ink">
          Saisissez le code affiché par votre application d&apos;authentification.
        </p>
      )}
      {(etape.statut === "code" || etape.statut === "enrolement") && (
        <form onSubmit={valider} className="mt-4 space-y-3">
          <SaisieCode
            valeur={saisie}
            onChange={(valeur) => {
              setSaisie(valeur);
              setRefus(null);
            }}
            invalide={refus !== null}
            idErreur={refus ? "refus-code" : undefined}
            disabled={envoi}
          />
          {refus && (
            <p id="refus-code" className="text-sm text-danger">
              {refus}
            </p>
          )}
          <Button type="submit" disabled={envoi}>
            {envoi ? "Vérification…" : "Valider"}
          </Button>
        </form>
      )}
      {etape.statut === "code" && (
        <p className="mt-6 text-sm text-subtle">
          Téléphone perdu ? Demandez à un autre administrateur de réinitialiser votre double
          authentification, depuis l&apos;écran Équipe.
        </p>
      )}
    </section>
  );
}
