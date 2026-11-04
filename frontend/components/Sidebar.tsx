"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Bell, FlaskConical, Landmark, LayoutGrid, Plug, Scale, Users } from "lucide-react";

import { Marque } from "@/components/Marque";
import {
  deconnecterGestionnaire,
  estPortefeuilleDemo,
  lireNomPortefeuille,
  obtenirSessionGestionnaire,
  renommerPortefeuille,
} from "@/lib/auth-gestionnaire";

const LIENS = [
  { href: "/portefeuille", libelle: "Entreprises", Icone: LayoutGrid },
  { href: "/expert", libelle: "Mode expert", Icone: Scale },
  { href: "/connexions-bancaires", libelle: "Connexions bancaires", Icone: Landmark },
  { href: "/rappels", libelle: "Rappels", Icone: Bell },
  { href: "/equipe", libelle: "Équipe", Icone: Users },
  { href: "/integrations", libelle: "Intégrations", Icone: Plug },
];

export function Sidebar() {
  const chemin = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [nom, setNom] = useState("Organisation");
  const [erreurNom, setErreurNom] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEmail(obtenirSessionGestionnaire()?.email ?? "");
    setDemo(estPortefeuilleDemo());
    lireNomPortefeuille()
      .then((valeur) => {
        if (valeur) setNom(valeur);
      })
      .catch(() => undefined);
  }, []);

  async function enregistrerNom() {
    const propre = nom.trim();
    if (!propre) return;
    setErreurNom(null);
    try {
      setNom(await renommerPortefeuille(propre));
    } catch (exception) {
      setErreurNom(exception instanceof Error ? exception.message : "Impossible d'enregistrer le nom.");
      const relu = await lireNomPortefeuille().catch(() => "");
      if (relu) setNom(relu);
    }
  }

  function seDeconnecter() {
    deconnecterGestionnaire();
    router.push("/connexion");
  }

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-border bg-canvas-app px-3 py-4">
      <div className="px-2 pb-4">
        <Marque />
      </div>
      <div className="mb-4 flex items-center gap-2 rounded-lg bg-canvas px-2.5 py-2">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-subtle text-xs font-semibold text-primary">
          {email.slice(0, 2).toUpperCase() || "AX"}
        </span>
        <span className="min-w-0 flex-1">
          <input
            value={nom}
            onChange={(evenement) => setNom(evenement.target.value)}
            onBlur={enregistrerNom}
            onKeyDown={(evenement) => {
              if (evenement.key === "Enter") {
                evenement.preventDefault();
                void enregistrerNom();
              }
            }}
            aria-label="Nom de l'organisation"
            className="w-full truncate bg-transparent text-sm font-semibold text-ink outline-none focus-visible:shadow-[0_0_0_3px_rgba(37,99,235,0.45)]"
          />
          <span className="block text-xs text-subtle">Organisation</span>
          {erreurNom && <span className="mt-1 block text-xs text-danger">{erreurNom}</span>}
        </span>
      </div>
      <nav aria-label="Gestionnaire" className="flex flex-1 flex-col gap-1">
        {LIENS.map(({ href, libelle, Icone }) => {
          const actif = chemin === href || chemin.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={actif ? "page" : undefined}
              className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors duration-150 ${
                actif ? "bg-canvas text-ink shadow-sm" : "text-subtle hover:bg-canvas hover:text-ink"
              }`}
            >
              <Icone className="h-4 w-4" aria-hidden />
              {libelle}
            </Link>
          );
        })}
      </nav>
      <div className="mt-4 border-t border-border pt-3">
        <p className="truncate px-2 text-xs text-subtle">{email}</p>
        {demo && (
          <Link
            href="/demo"
            aria-current={chemin === "/demo" || chemin.startsWith("/demo/") ? "page" : undefined}
            className={`mt-1 flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm ${
              chemin === "/demo" || chemin.startsWith("/demo/")
                ? "bg-canvas font-medium text-ink"
                : "text-subtle hover:bg-canvas hover:text-ink"
            }`}
          >
            <FlaskConical className="h-4 w-4" aria-hidden />
            Démo
          </Link>
        )}
        <Link
          href="/compte"
          aria-current={chemin === "/compte" || chemin.startsWith("/compte/") ? "page" : undefined}
          className={`mt-1 block rounded-lg px-2 py-1.5 text-sm ${
            chemin === "/compte" || chemin.startsWith("/compte/")
              ? "bg-canvas font-medium text-ink"
              : "text-subtle hover:bg-canvas hover:text-ink"
          }`}
        >
          Compte
        </Link>
        <button
          type="button"
          onClick={seDeconnecter}
          className="mt-1 w-full rounded-lg px-2 py-1.5 text-left text-sm text-subtle hover:bg-canvas hover:text-ink"
        >
          Se déconnecter
        </button>
      </div>
    </aside>
  );
}
