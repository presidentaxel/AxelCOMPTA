import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { TEXTES_JURIDIQUES, estCleTexte, lireTexte, type Bloc, type Morceau } from "@/lib/juridique";

/** AXE-859 : les textes juridiques, lus au build depuis `docs/juridique/`
 * (seule source, versionnée et relue avec AXE-813). Pages publiques : un
 * dirigeant invité doit pouvoir les lire avant de se connecter. */
export function generateStaticParams() {
  return Object.keys(TEXTES_JURIDIQUES).map((texte) => ({ texte }));
}

export const dynamicParams = false;

type Parametres = { params: Promise<{ texte: string }> };

export async function generateMetadata({ params }: Parametres): Promise<Metadata> {
  const { texte } = await params;
  return { title: estCleTexte(texte) ? `${TEXTES_JURIDIQUES[texte]} · AxeL` : "AxeL" };
}

function lire(cle: string): string {
  return readFileSync(join(process.cwd(), "..", "docs", "juridique", `${cle}.md`), "utf8");
}

export default async function TexteJuridique({ params }: Parametres) {
  const { texte } = await params;
  if (!estCleTexte(texte)) notFound();
  const blocs = lireTexte(lire(texte));
  return (
    <main className="mx-auto max-w-2xl px-4 py-10 text-sm leading-relaxed text-ink">
      {blocs.map((bloc, rang) => (
        <BlocJuridique key={rang} bloc={bloc} />
      ))}
      <nav aria-label="Textes juridiques" className="mt-10 border-t border-border pt-4">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-subtle">
          {Object.entries(TEXTES_JURIDIQUES).map(([cle, titre]) => (
            <li key={cle}>
              <Link href={`/legal/${cle}`} className="inline-flex min-h-11 items-center text-primary">
                {titre}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </main>
  );
}

function Morceaux({ morceaux }: { morceaux: Morceau[] }) {
  return (
    <>
      {morceaux.map((m, rang) => {
        if (m.type === "gras") return <strong key={rang}>{m.texte}</strong>;
        if (m.type === "lien") {
          return (
            <Link key={rang} href={`/legal/${m.cle}`} className="font-medium text-primary">
              {m.texte}
            </Link>
          );
        }
        return <span key={rang}>{m.texte}</span>;
      })}
    </>
  );
}

function BlocJuridique({ bloc }: { bloc: Bloc }) {
  switch (bloc.type) {
    case "titre":
      if (bloc.niveau === 1) {
        return (
          <h1 className="text-xl font-semibold">
            <Morceaux morceaux={bloc.morceaux} />
          </h1>
        );
      }
      return (
        <h2 className={bloc.niveau === 2 ? "mt-8 text-base font-semibold" : "mt-6 font-semibold"}>
          <Morceaux morceaux={bloc.morceaux} />
        </h2>
      );
    case "encadre":
      return (
        <p className="mt-3 rounded-md border border-warning/40 bg-pending-subtle p-3 text-subtle">
          <Morceaux morceaux={bloc.morceaux} />
        </p>
      );
    case "paragraphe":
      return (
        <p className="mt-3">
          <Morceaux morceaux={bloc.morceaux} />
        </p>
      );
    case "liste": {
      const Liste = bloc.ordonnee ? "ol" : "ul";
      return (
        <Liste className={`mt-3 space-y-1 pl-5 ${bloc.ordonnee ? "list-decimal" : "list-disc"}`}>
          {bloc.elements.map((element, rang) => (
            <li key={rang}>
              <Morceaux morceaux={element} />
            </li>
          ))}
        </Liste>
      );
    }
    case "tableau":
      return (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr>
                {bloc.entete.map((cellule, rang) => (
                  <th key={rang} className="border-b border-border py-2 pr-3 font-medium">
                    <Morceaux morceaux={cellule} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bloc.lignes.map((ligne, rang) => (
                <tr key={rang}>
                  {ligne.map((cellule, i) => (
                    <td key={i} className="border-b border-border py-2 pr-3 align-top">
                      <Morceaux morceaux={cellule} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
  }
}
