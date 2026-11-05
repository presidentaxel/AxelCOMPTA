"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { obtenirSessionGestionnaire } from "@/lib/auth-gestionnaire";

const PREVUES = [
  {
    nom: "Rollee",
    detail: "Lirait les courses et les versements Uber, Bolt et Heetch de chaque chauffeur.",
  },
  {
    nom: "Bridge",
    detail: "Connecterait la banque en direct, en plus de Digifactory.",
  },
  {
    nom: "Volubile",
    detail: "Passerait les appels des relances configurées dans Rappels.",
  },
  {
    nom: "SMS",
    detail: "Enverrait les relances par SMS.",
  },
  {
    nom: "E-mail",
    detail: "Enverrait les relances par e-mail, à part de l'invitation de compte.",
  },
];

/** Digifactory est le canal bancaire du portefeuille : les comptes des
 * entreprises arrivent par lui, l'app chauffeur ne propose donc pas de
 * connecter sa banque. Les autres intégrations sont annoncées, pas branchées. */
export default function IntegrationsPage() {
  const router = useRouter();

  useEffect(() => {
    if (obtenirSessionGestionnaire() === null) {
      router.replace("/connexion");
    }
  }, [router]);

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Intégrations</h1>
      <p className="mt-2 text-sm text-subtle">
        Digifactory apporte les comptes bancaires des entreprises. Le reste n&apos;est pas encore
        connecté.
      </p>
      <ul className="mt-8">
        <li className="flex items-start justify-between gap-6 border-b border-hairline py-4">
          <span>
            <span className="block text-sm font-medium text-ink">Digifactory</span>
            <span className="mt-1 block text-sm text-subtle">
              Branché. Les opérations arrivent chaque heure ; l&apos;état de chaque banque est dans
              Connexions bancaires.
            </span>
          </span>
          <span className="shrink-0 text-xs text-subtle">Branché</span>
        </li>
        {PREVUES.map((integration) => (
          <li
            key={integration.nom}
            className="flex items-start justify-between gap-6 border-b border-hairline py-4"
          >
            <span>
              <span className="block text-sm font-medium text-ink">{integration.nom}</span>
              <span className="mt-1 block text-sm text-subtle">{integration.detail}</span>
            </span>
            <span className="shrink-0 text-xs text-subtle">Prévu</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
