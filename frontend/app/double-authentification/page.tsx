"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useState } from "react";

import { MessageAcces } from "@/components/MessageAcces";
import { TitreAcces } from "@/components/PageAcces";
import { SaisieCode } from "@/components/SaisieCode";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
import { messageErreurMfa } from "@/lib/messages-mfa";
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
  const idRefus = useId();
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
      setEtape({ statut: "erreur", message: messageErreurMfa(exception, "preparation") });
    }
  }, [router]);

  useEffect(() => {
    // Une fois : `preparer` ne change que si le routeur change, ce qui
    // refairait un QR. Le routeur de Next garde la même identité.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void preparer();
  }, [preparer]);

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
      setRefus(messageErreurMfa(exception, "verification"));
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <section aria-labelledby="titre-double-auth">
      <TitreAcces id="titre-double-auth">Double authentification</TitreAcces>
      {etape.statut === "chargement" && <SqueletteDoubleAuth />}
      {etape.statut === "erreur" && (
        <div className="mt-8 space-y-4">
          <MessageAcces ton="erreur">{etape.message}</MessageAcces>
          <Button type="button" onClick={() => void preparer()}>
            Réessayer
          </Button>
        </div>
      )}
      {etape.statut === "enrolement" && (
        <div className="mt-4 space-y-6">
          <p className="text-base text-body">
            Votre rôle demande un code en plus du mot de passe. Scannez ce QR code avec une
            application d&apos;authentification (Google Authenticator, 1Password, Authy…), puis
            saisissez le code qu&apos;elle affiche.
          </p>
          {/* Le QR se scanne sur fond blanc : la carte et le cadre sont en `canvas`. */}
          <Card className="flex flex-col items-center gap-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={etape.enrolement.qrCode}
              alt="QR code à scanner avec votre application d'authentification"
              className="size-52 bg-canvas p-2"
            />
            <p className="w-full text-sm text-subtle">
              Sans appareil photo, saisissez cette clé :{" "}
              <code className="select-all break-all font-mono text-ink">
                {etape.enrolement.secret}
              </code>
            </p>
          </Card>
        </div>
      )}
      {etape.statut === "code" && (
        <p className="mt-4 text-base text-body">
          Saisissez le code affiché par votre application d&apos;authentification.
        </p>
      )}
      {(etape.statut === "code" || etape.statut === "enrolement") && (
        <form onSubmit={valider} className="mt-6 space-y-4">
          <SaisieCode
            valeur={saisie}
            onChange={(valeur) => {
              setSaisie(valeur);
              setRefus(null);
            }}
            invalide={refus !== null}
            idErreur={refus ? idRefus : undefined}
            disabled={envoi}
          />
          {refus && (
            <MessageAcces ton="erreur" id={idRefus}>
              {refus}
            </MessageAcces>
          )}
          <Button type="submit" disabled={envoi} className="w-full">
            {envoi ? "Vérification…" : "Valider"}
          </Button>
        </form>
      )}
      {etape.statut === "code" && (
        <p className="mt-8 border-t border-border pt-6 text-sm text-subtle">
          Téléphone perdu ? Demandez à un autre administrateur de réinitialiser votre double
          authentification, depuis l&apos;écran Équipe.
        </p>
      )}
    </section>
  );
}

/** Même emprise que l'enrôlement (le cas le plus haut) : rien ne saute quand
 * la page répond. `role="status"` : le lecteur d'écran dit que ça charge. */
function SqueletteDoubleAuth() {
  return (
    <div role="status" aria-busy="true" className="mt-4 space-y-6">
      <span className="sr-only">Préparation de la double authentification…</span>
      <div className="space-y-2" aria-hidden>
        <Squelette className="h-4 w-full" />
        <Squelette className="h-4 w-2/3" />
      </div>
      <Squelette className="h-72 w-full" />
      <div className="grid grid-cols-6 gap-2 sm:gap-3" aria-hidden>
        {Array.from({ length: 6 }, (_, index) => (
          <Squelette key={index} className="h-11" />
        ))}
      </div>
    </div>
  );
}
