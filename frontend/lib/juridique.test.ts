import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

import { TEXTES_JURIDIQUES, lireMorceaux, lireTexte, type CleTexte } from "./juridique";

test("gras et lien vers un autre texte ; un lien externe garde son texte", () => {
  assert.deepEqual(lireMorceaux("Le **client** voit [Confidentialité](confidentialite.md)."), [
    { type: "texte", texte: "Le " },
    { type: "gras", texte: "client" },
    { type: "texte", texte: " voit " },
    { type: "lien", texte: "Confidentialité", cle: "confidentialite" },
    { type: "texte", texte: "." },
  ]);
  assert.deepEqual(lireMorceaux("Voir [doc 10](../10-securite-rgpd.md) et `code`"), [
    { type: "texte", texte: "Voir " },
    { type: "texte", texte: "doc 10" },
    { type: "texte", texte: " et code" },
  ]);
});

test("titres, paragraphes sur plusieurs lignes, listes, citation, tableau", () => {
  const blocs = lireTexte(
    [
      "# Titre",
      "",
      "> Version du 2026-11-10.",
      "> Projet.",
      "",
      "Une phrase",
      "sur deux lignes.",
      "",
      "- un",
      "- deux qui",
      "  continue",
      "",
      "1. premier",
      "2. second",
      "",
      "| A | B |",
      "|---|---|",
      "| 1 | **2** |",
    ].join("\n"),
  );
  assert.deepEqual(
    blocs.map((b) => b.type),
    ["titre", "encadre", "paragraphe", "liste", "liste", "tableau"],
  );
  assert.deepEqual(blocs[1], { type: "encadre", morceaux: [{ type: "texte", texte: "Version du 2026-11-10. Projet." }] });
  assert.deepEqual(blocs[2], { type: "paragraphe", morceaux: [{ type: "texte", texte: "Une phrase sur deux lignes." }] });
  const liste = blocs[3];
  assert.equal(liste?.type === "liste" && liste.elements.length, 2);
  assert.deepEqual(liste?.type === "liste" && liste.elements[1], [{ type: "texte", texte: "deux qui continue" }]);
  const tableau = blocs[5];
  assert.equal(tableau?.type === "tableau" && tableau.lignes[0]?.[1]?.[0]?.type, "gras");
});

// Critères d'AXE-859, vérifiés sur les textes eux-mêmes : si un service
// change dans le code, ce test oblige à revoir les textes.
const DOSSIER = join(process.cwd(), "..", "docs", "juridique");
function lire(cle: CleTexte): string {
  return readFileSync(join(DOSSIER, `${cle}.md`), "utf8");
}
const TOUS = (Object.keys(TEXTES_JURIDIQUES) as CleTexte[]).map(lire).join("\n");

test("les textes citent Supabase en eu-west-1 et Digifactory", () => {
  assert.match(lire("confidentialite"), /Supabase/u);
  assert.match(lire("confidentialite"), /eu-west-1/u);
  assert.match(lire("mentions-legales"), /eu-west-1/u);
  assert.match(lire("confidentialite"), /Digifactory/u);
});

test("le fournisseur d'IA n'est cité que dans la confidentialité, pseudonymisation comprise", () => {
  // AXE-887 : l'étage LLM (Anthropic) est branché, éteint par défaut.
  const confidentialite = lire("confidentialite");
  assert.match(confidentialite, /Anthropic/u);
  assert.match(confidentialite, /pseudonymisés/u);
  const autres = (Object.keys(TEXTES_JURIDIQUES) as CleTexte[])
    .filter((cle) => cle !== "confidentialite")
    .map(lire)
    .join("\n");
  assert.doesNotMatch(autres, /\b(LLM|Claude|Gemini|OpenAI|GPT|Mistral|Anthropic)\b/u);
});

test("les plateformes passent par Rollee, cité comme service", () => {
  // AXE-818 à AXE-821 : Rollee lit les revenus des plateformes.
  const tableau = lire("confidentialite")
    .split("\n")
    .filter((ligne) => ligne.startsWith("|"));
  assert.ok(tableau.some((ligne) => /Rollee/u.test(ligne)));
});

test("aucun prix : le seul montant est le capital de l'éditeur", () => {
  const montants = TOUS.match(/\d[\d\s]*(?:,\d+)?\s?€/gu) ?? [];
  assert.deepEqual(montants, ["100 €"]);
  assert.doesNotMatch(TOUS, /€\s*(HT|TTC)|\/\s*mois|par mois/u);
});

test("Bridge n'est jamais un sous-traitant ni un appel direct du produit", () => {
  const confidentialite = lire("confidentialite");
  const tableau = confidentialite.split("\n").filter((ligne) => ligne.startsWith("|"));
  assert.ok(tableau.length > 0);
  assert.ok(tableau.every((ligne) => !/Bridge/u.test(ligne)));
  assert.match(confidentialite, /n'interroge pas les banques/u);
});

test("l'engagement de l'expert reprend mot pour mot le texte accepté dans l'app", () => {
  const code = readFileSync(
    join(process.cwd(), "..", "backend", "axelcompta", "workflow", "expert_comptable.py"),
    "utf8",
  );
  const bloc = /TEXTE_ENGAGEMENT = \(([\s\S]*?)\n\)/u.exec(code)?.[1] ?? "";
  const texte = [...bloc.matchAll(/"((?:[^"\\]|\\.)*)"/gu)].map((m) => m[1]).join("");
  const version = /VERSION_ENGAGEMENT = "([^"]+)"/u.exec(code)?.[1] ?? "";
  assert.ok(texte.length > 100);
  const md = lire("engagement-expert-comptable");
  assert.ok(md.includes(texte), "le texte du fichier ne suit plus TEXTE_ENGAGEMENT");
  assert.ok(md.includes(`Version ${version}`));
});
