"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { brancherIntegrationEnvoi } from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";

const CHAMPS = {
  mail: {
    nom: "E-mail",
    fournisseur: "smtp",
    detail: "Votre serveur SMTP envoie les rappels aux chauffeurs.",
    champs: [
      ["hote", "Serveur SMTP", "text"],
      ["port", "Port (587 ou 465)", "number"],
      ["utilisateur", "Utilisateur", "text"],
      ["mot_de_passe", "Mot de passe", "password"],
      ["expediteur", "Adresse d'expédition", "email"],
    ],
  },
  sms: {
    nom: "SMS",
    fournisseur: "http",
    detail: "Votre fournisseur de SMS (API HTTP) envoie les rappels courts.",
    champs: [
      ["url", "Adresse de l'API d'envoi", "url"],
      ["cle_api", "Clé d'API", "password"],
      ["expediteur", "Nom d'expéditeur", "text"],
    ],
  },
} as const;

/** AXE-808 : brancher l'e-mail ou le SMS du gestionnaire. Les identifiants
 * sont chiffrés par l'API et ne reviennent jamais : l'écran dit seulement
 * « Branché le… ». Rebrancher remplace les précédents. */
export function IntegrationEnvoi({
  canal,
  branche,
  admin,
  onBranche,
}: {
  canal: "mail" | "sms";
  branche: string | undefined;
  admin: boolean;
  onBranche: (canaux: Record<string, string>) => void;
}) {
  const config = CHAMPS[canal];
  const [ouvert, setOuvert] = useState(false);
  const [valeurs, setValeurs] = useState<Record<string, string>>({});
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function enregistrer(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnvoi(true);
    setErreur(null);
    try {
      onBranche(await brancherIntegrationEnvoi(canal, config.fournisseur, valeurs));
      setValeurs({});
      setOuvert(false);
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Échec du branchement.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <li className="border-b border-hairline py-4">
      <div className="flex items-start justify-between gap-6">
        <span>
          <span className="block text-sm font-medium text-ink">{config.nom}</span>
          <span className="mt-1 block text-sm text-subtle">{config.detail}</span>
        </span>
        <span className="shrink-0 text-xs text-subtle">
          {branche ? `Branché le ${formatDate(branche.slice(0, 10))}` : "À brancher"}
        </span>
      </div>
      {admin && !ouvert && (
        <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={() => setOuvert(true)}>
          {branche ? "Changer les identifiants" : "Brancher"}
        </Button>
      )}
      {ouvert && (
        <form onSubmit={enregistrer} className="mt-3 space-y-2">
          {config.champs.map(([cle, libelle, type]) => (
            <label key={cle} className="block text-sm text-ink">
              {libelle}
              <Input
                type={type}
                required
                autoComplete="off"
                value={valeurs[cle] ?? ""}
                onChange={(e) => setValeurs((v) => ({ ...v, [cle]: e.target.value }))}
                className="mt-1"
              />
            </label>
          ))}
          {erreur && <p className="text-sm text-danger">{erreur}</p>}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={envoi}>
              {envoi ? "Enregistrement…" : "Enregistrer"}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setOuvert(false)}>
              Annuler
            </Button>
          </div>
        </form>
      )}
    </li>
  );
}
