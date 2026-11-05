import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  absenceDeCompte,
  LONGUEUR_MIN_MOT_DE_PASSE,
  MESSAGE_EMAIL_NON_CONFIRME,
  MESSAGE_GENERIQUE,
  MESSAGE_IDENTIFIANTS,
  MESSAGE_INVITATION,
  MESSAGE_LIEN_EXPIRE,
  MESSAGE_MEME_MOT_DE_PASSE,
  MESSAGE_MOT_DE_PASSE_COURT,
  MESSAGE_MOT_DE_PASSE_FAIBLE,
  MESSAGE_RESEAU,
  MESSAGE_SERVICE,
  MESSAGE_TROP_D_EMAILS,
  MESSAGE_TROP_DE_TENTATIVES,
  messageMotDePasseCourt,
  messageParametresAuth,
  traduireCorpsAuth,
  traduireExceptionAuth,
  traduireTexteAuth,
} from "./messages-auth";

class ErreurAuthChauffeur extends Error {
  override name = "ErreurAuthChauffeur";
}

describe("traduireCorpsAuth", () => {
  it("traduit un mot de passe refusé (forme actuelle)", () => {
    const message = traduireCorpsAuth(
      { code: 400, error_code: "invalid_credentials", msg: "Invalid login credentials" },
      400,
    );
    assert.equal(message, MESSAGE_IDENTIFIANTS);
    assert.equal(contientAction(message), true);
  });

  it("traduit un mot de passe refusé (forme ancienne)", () => {
    assert.equal(
      traduireCorpsAuth(
        { error: "invalid_grant", error_description: "Invalid login credentials" },
        400,
      ),
      MESSAGE_IDENTIFIANTS,
    );
  });

  it("traduit une adresse non confirmée", () => {
    assert.equal(
      traduireCorpsAuth({ error_code: "email_not_confirmed", msg: "Email not confirmed" }, 400),
      MESSAGE_EMAIL_NON_CONFIRME,
    );
  });

  it("traduit un mot de passe trop court, sans reprendre le minimum anglais", () => {
    assert.equal(
      traduireCorpsAuth(
        {
          error_code: "weak_password",
          msg: "Password should be at least 6 characters.",
          weak_password: { reasons: ["length"], message: "Password should be at least 6 characters." },
        },
        422,
      ),
      MESSAGE_MOT_DE_PASSE_COURT,
    );
  });

  it("reprend un minimum serveur plus exigeant que 8", () => {
    assert.equal(
      traduireCorpsAuth(
        {
          error_code: "weak_password",
          msg: "Password should be at least 12 characters.",
          weak_password: { reasons: ["length"] },
        },
        422,
      ),
      "Choisissez un mot de passe d'au moins 12 caractères.",
    );
  });

  it("traduit un mot de passe déjà compromis", () => {
    assert.equal(
      traduireCorpsAuth(
        {
          error_code: "weak_password",
          msg: "Password is known to be weak and easy to guess, please choose a different one.",
          weak_password: { reasons: ["pwned"] },
        },
        422,
      ),
      MESSAGE_MOT_DE_PASSE_FAIBLE,
    );
  });

  it("traduit un mot de passe identique à l'actuel", () => {
    assert.equal(
      traduireCorpsAuth(
        {
          error_code: "same_password",
          msg: "New password should be different from the old password.",
        },
        422,
      ),
      MESSAGE_MEME_MOT_DE_PASSE,
    );
  });

  it("traduit un plafond d'e-mails", () => {
    assert.equal(
      traduireCorpsAuth(
        {
          error_code: "over_email_send_rate_limit",
          msg: "For security purposes, you can only request this once every 60 seconds",
        },
        429,
      ),
      MESSAGE_TROP_D_EMAILS,
    );
  });

  it("traduit un plafond de tentatives sans code", () => {
    assert.equal(traduireCorpsAuth({ msg: "Request rate limit reached" }, 429), MESSAGE_TROP_DE_TENTATIVES);
  });

  it("traduit une panne du service", () => {
    assert.equal(traduireCorpsAuth({ message: "Internal Server Error" }, 500), MESSAGE_SERVICE);
  });

  it("ne laisse pas passer l'anglais d'une erreur inconnue", () => {
    const message = traduireCorpsAuth({ msg: "Something went wrong in the upstream" }, 400);
    assert.equal(message, MESSAGE_GENERIQUE);
    assert.equal(/[A-Za-z]{4}/.test(message) && message.includes("Something"), false);
  });
});

describe("réseau", () => {
  it("traduit Failed to fetch, NetworkError et Load failed", () => {
    assert.equal(traduireExceptionAuth(new TypeError("Failed to fetch")), MESSAGE_RESEAU);
    assert.equal(
      traduireExceptionAuth(new TypeError("NetworkError when attempting to fetch resource.")),
      MESSAGE_RESEAU,
    );
    assert.equal(traduireExceptionAuth(new TypeError("Load failed")), MESSAGE_RESEAU);
    assert.equal(traduireTexteAuth("fetch failed"), MESSAGE_RESEAU);
  });

  it("garde un message déjà français", () => {
    const erreur = new ErreurAuthChauffeur(MESSAGE_IDENTIFIANTS);
    assert.equal(traduireExceptionAuth(erreur), MESSAGE_IDENTIFIANTS);
  });
});

describe("lien consommé ou expiré", () => {
  it("traduit le fragment laissé par un logiciel de messagerie", () => {
    const parametres = new URLSearchParams(
      "error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired",
    );
    assert.equal(messageParametresAuth(parametres), MESSAGE_LIEN_EXPIRE);
  });

  it("traduit un jeton à usage unique déjà pris", () => {
    assert.equal(
      traduireCorpsAuth({ error_code: "flow_state_expired", msg: "One-time token not found" }, 403),
      MESSAGE_LIEN_EXPIRE,
    );
  });

  it("traduit une invitation introuvable", () => {
    assert.equal(
      traduireCorpsAuth({ error_code: "invite_not_found", msg: "Invite not found" }, 404),
      MESSAGE_INVITATION,
    );
  });

  it("ignore une URL sans erreur", () => {
    assert.equal(messageParametresAuth(new URLSearchParams("code=abc")), null);
  });
});

describe("absenceDeCompte", () => {
  it("reconnaît l'adresse inconnue du lien magique sans la montrer", () => {
    const corps = { code: 422, error_code: "otp_disabled", msg: "Signups not allowed for otp" };
    assert.equal(absenceDeCompte(corps), true);
  });

  it("reconnaît user not found", () => {
    assert.equal(absenceDeCompte({ error_code: "user_not_found", msg: "User not found" }), true);
  });

  it("ne confond pas un mauvais mot de passe avec une adresse inconnue", () => {
    assert.equal(absenceDeCompte({ error_code: "invalid_credentials", msg: "Invalid login credentials" }), false);
  });
});

describe("messageMotDePasseCourt", () => {
  it("refuse moins de 8 caractères et garde les espaces", () => {
    assert.equal(messageMotDePasseCourt("court"), MESSAGE_MOT_DE_PASSE_COURT);
    assert.equal(messageMotDePasseCourt("1234567"), MESSAGE_MOT_DE_PASSE_COURT);
    assert.equal(messageMotDePasseCourt("12345678"), null);
    assert.equal(messageMotDePasseCourt("       x"), null);
    assert.equal(LONGUEUR_MIN_MOT_DE_PASSE, 8);
  });
});

function contientAction(message: string): boolean {
  return /réessayez|utilisez|demandez|choisissez|patientez|ouvrez|reconnectez|contactez/i.test(message);
}
