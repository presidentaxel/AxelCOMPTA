import assert from "node:assert/strict";
import test from "node:test";

import {
  LONGUEUR_MAX,
  MESSAGE_INJOIGNABLE,
  SAISIE_VIDE,
  champDeLaPhrase,
  corpsDeLaDemande,
  envoyerLaDemande,
  premiereErreur,
  resultatApresReponse,
  type SaisieEchange,
} from "./demande-echange";

const VALIDE: SaisieEchange = {
  nom: "Claire Martin",
  email: "claire@cabinet-martin.fr",
  organisation: "Cabinet Martin",
  profil: "cabinet",
  message: "",
  siteWeb: "",
};

test("une saisie complète n'a pas d'erreur, le message est facultatif", () => {
  assert.equal(premiereErreur(VALIDE), null);
});

test("la première erreur suit l'ordre du formulaire, avec la phrase du serveur", () => {
  assert.deepEqual(premiereErreur(SAISIE_VIDE), { champ: "nom", message: "Indiquez votre nom." });
  assert.deepEqual(premiereErreur({ ...VALIDE, email: "claire@cabinet" }), {
    champ: "email",
    message: "Indiquez une adresse e-mail valide.",
  });
  assert.deepEqual(premiereErreur({ ...VALIDE, organisation: "  " }), {
    champ: "organisation",
    message: "Indiquez votre organisation.",
  });
  assert.deepEqual(premiereErreur({ ...VALIDE, profil: "" }), {
    champ: "profil",
    message: "Indiquez si vous êtes un cabinet ou une centrale.",
  });
});

test("un champ trop long dit sa limite", () => {
  const erreur = premiereErreur({ ...VALIDE, message: "x".repeat(LONGUEUR_MAX.message + 1) });
  assert.equal(erreur?.champ, "message");
  assert.match(erreur?.message ?? "", /2000 caractères au plus/u);
  assert.equal(premiereErreur({ ...VALIDE, message: "x".repeat(LONGUEUR_MAX.message) }), null);
});

test("le corps envoyé est nettoyé, le message vide devient absent", () => {
  assert.deepEqual(corpsDeLaDemande({ ...VALIDE, nom: " Claire Martin ", message: "  " }), {
    nom: "Claire Martin",
    email: "claire@cabinet-martin.fr",
    organisation: "Cabinet Martin",
    role: "cabinet",
    message: null,
    site_web: "",
  });
});

test("un succès reprend le message du serveur", () => {
  assert.deepEqual(resultatApresReponse(201, { message: "Merci." }), { statut: "envoyee", message: "Merci." });
  assert.equal(resultatApresReponse(201, {}).statut, "envoyee");
});

test("un refus reprend la phrase du serveur et désigne le champ", () => {
  assert.deepEqual(resultatApresReponse(422, { detail: "Indiquez une adresse e-mail valide." }), {
    statut: "refusee",
    champ: "email",
    message: "Indiquez une adresse e-mail valide.",
  });
  assert.equal(resultatApresReponse(429, { detail: "Trop de demandes pour le moment. Réessayez dans quelques minutes." }).statut, "refusee");
});

test("une liste d'erreurs de validation n'arrive jamais à l'écran", () => {
  const resultat = resultatApresReponse(422, { detail: [{ loc: ["body", "nom"], msg: "too long" }] });
  assert.equal(resultat.statut, "refusee");
  assert.equal(resultat.message, "La demande n'a pas pu être envoyée. Réessayez dans un instant.");
  assert.equal(resultat.statut === "refusee" && resultat.champ, null);
});

test("chaque phrase du serveur retombe sur son champ", () => {
  assert.equal(champDeLaPhrase("Indiquez votre nom."), "nom");
  assert.equal(champDeLaPhrase("Le champ « nom » est trop long (100 caractères au plus)."), "nom");
  assert.equal(champDeLaPhrase("Indiquez une adresse e-mail valide."), "email");
  assert.equal(champDeLaPhrase("Indiquez votre organisation."), "organisation");
  assert.equal(champDeLaPhrase("Indiquez si vous êtes un cabinet ou une centrale."), "profil");
  assert.equal(champDeLaPhrase("Le champ « message » est trop long (2000 caractères au plus)."), "message");
  assert.equal(champDeLaPhrase("Trop de demandes pour le moment."), null);
});

test("l'envoi poste le corps en JSON sur la route publique", async () => {
  let vu: { url: string; init: RequestInit | undefined } | null = null;
  const appel = (async (url: string, init?: RequestInit) => {
    vu = { url, init };
    return new Response(JSON.stringify({ message: "Merci." }), { status: 201 });
  }) as unknown as typeof fetch;
  const resultat = await envoyerLaDemande(VALIDE, "http://api.test", appel);
  assert.equal(resultat.statut, "envoyee");
  const requete = vu as { url: string; init: RequestInit | undefined } | null;
  assert.equal(requete?.url, "http://api.test/demandes-echange");
  assert.equal(requete?.init?.method, "POST");
  assert.equal(JSON.parse(String(requete?.init?.body)).role, "cabinet");
});

test("un serveur muet est dit, sans erreur technique", async () => {
  const appel = (async () => {
    throw new TypeError("fetch failed");
  }) as unknown as typeof fetch;
  assert.deepEqual(await envoyerLaDemande(VALIDE, "http://api.test", appel), {
    statut: "injoignable",
    message: MESSAGE_INJOIGNABLE,
  });
});

test("une réponse sans corps lisible reste une erreur dite en français", async () => {
  const appel = (async () => new Response("<html>", { status: 502 })) as unknown as typeof fetch;
  const resultat = await envoyerLaDemande(VALIDE, "http://api.test", appel);
  assert.equal(resultat.statut, "refusee");
  assert.match(resultat.message, /Réessayez/u);
});
