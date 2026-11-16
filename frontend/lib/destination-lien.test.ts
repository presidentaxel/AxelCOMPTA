import assert from "node:assert/strict";
import test from "node:test";

import { destinationLienAuth, repriseLienAuth } from "./destination-lien";

function jeton(charge: Record<string, unknown>): string {
  const corps = Buffer.from(JSON.stringify(charge)).toString("base64url");
  return `entete.${corps}.signature`;
}

const FRAGMENT_RECOVERY = "#access_token=abc&refresh_token=def&type=recovery";

test("un fragment de réinitialisation quitte le portefeuille pour le choix du mot de passe", () => {
  const cible = destinationLienAuth("/portefeuille", "", FRAGMENT_RECOVERY);
  assert.equal(cible, `/auth/lien${FRAGMENT_RECOVERY}`);
  assert.deepEqual(repriseLienAuth("/portefeuille", "", FRAGMENT_RECOVERY), {
    action: "rediriger",
    url: `/auth/lien${FRAGMENT_RECOVERY}`,
  });
});

test("le côté demandé dans l'adresse est conservé", () => {
  assert.equal(
    destinationLienAuth("/portefeuille", "?cote=gestionnaire", FRAGMENT_RECOVERY),
    `/auth/lien?cote=gestionnaire${FRAGMENT_RECOVERY}`,
  );
});

test("la page du lien ne se renvoie pas vers la connexion", () => {
  assert.equal(destinationLienAuth("/auth/lien", "", FRAGMENT_RECOVERY), null);
  assert.deepEqual(repriseLienAuth("/auth/lien", "", FRAGMENT_RECOVERY), { action: "rester" });
  assert.deepEqual(repriseLienAuth("/chauffeur/accepter-invitation", "", FRAGMENT_RECOVERY), {
    action: "rester",
  });
});

test("une invitation chauffeur va choisir son mot de passe sur sa page", () => {
  const fragment = `#access_token=${jeton({ app_metadata: { dossier_id: "d1" } })}&refresh_token=r&type=invite`;
  assert.equal(
    destinationLienAuth("/", "", fragment),
    `/chauffeur/accepter-invitation${fragment}`,
  );
});

test("une invitation d'équipe va choisir son mot de passe sur la page du lien", () => {
  const fragment = `#access_token=${jeton({ app_metadata: { tenant_id: "T1" } })}&refresh_token=r&type=invite`;
  assert.equal(destinationLienAuth("/portefeuille", "", fragment), `/auth/lien${fragment}`);
});

test("une erreur Supabase dans l'adresse n'est pas une session expirée", () => {
  assert.equal(
    destinationLienAuth("/portefeuille", "?error=access_denied&error_code=otp_expired", ""),
    "/auth/lien?error=access_denied&error_code=otp_expired",
  );
  assert.equal(
    destinationLienAuth("/", "", "#error=access_denied&error_code=otp_expired"),
    "/auth/lien#error=access_denied&error_code=otp_expired",
  );
});

test("une adresse ordinaire du portefeuille ne change pas", () => {
  assert.equal(destinationLienAuth("/portefeuille", "?q=karim", ""), null);
  assert.deepEqual(repriseLienAuth("/portefeuille", "?q=karim", ""), { action: "aucune" });
});
