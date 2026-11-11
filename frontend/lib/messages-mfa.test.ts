import assert from "node:assert/strict";
import test from "node:test";

import {
  MESSAGE_CODE_INCORRECT,
  MESSAGE_PREPARATION,
  messageErreurMfa,
} from "./messages-mfa";
import { MESSAGE_RESEAU, MESSAGE_TROP_DE_TENTATIVES } from "./messages-auth";

test("un refus anglais de Supabase devient « code incorrect », sans fuite", () => {
  const message = messageErreurMfa(new Error("Invalid TOTP code entered"), "verification");
  assert.equal(message, MESSAGE_CODE_INCORRECT);
  assert.equal(/totp|invalid/i.test(message), false);
});

test("les messages de repli français de lib/mfa.ts passent tels quels", () => {
  assert.equal(
    messageErreurMfa(new Error("Impossible de lire votre compte."), "preparation"),
    "Impossible de lire votre compte.",
  );
  assert.equal(
    messageErreurMfa(new Error("Impossible de vérifier le code."), "verification"),
    "Impossible de vérifier le code.",
  );
});

test("le réseau et la limite de tentatives gardent leur message", () => {
  assert.equal(messageErreurMfa(new TypeError("Failed to fetch"), "verification"), MESSAGE_RESEAU);
  assert.equal(messageErreurMfa(new TypeError("Failed to fetch"), "preparation"), MESSAGE_RESEAU);
  assert.equal(
    messageErreurMfa(new Error("Request rate limit reached"), "verification"),
    MESSAGE_TROP_DE_TENTATIVES,
  );
});

test("à la préparation, un texte inconnu ne fuit pas non plus", () => {
  assert.equal(messageErreurMfa(new Error("JWT expired"), "preparation"), MESSAGE_PREPARATION);
  assert.equal(messageErreurMfa("autre chose", "preparation"), MESSAGE_PREPARATION);
  assert.equal(messageErreurMfa(undefined, "verification"), MESSAGE_CODE_INCORRECT);
});

test("à la vérification, une phrase d'un autre domaine ne remplace pas le refus", () => {
  // « has expired » se traduit en « lien expiré » ailleurs : hors sujet ici.
  assert.equal(
    messageErreurMfa(new Error("Challenge has expired"), "verification"),
    MESSAGE_CODE_INCORRECT,
  );
});
