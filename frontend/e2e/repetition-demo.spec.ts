import { expect, test, type Page, type Route } from "@playwright/test";

/** Jeton non signé : le navigateur ne vérifie que la date d'expiration.
 * La signature est l'affaire de l'API, couverte par les tests Python. */
function jeton(claims: Record<string, unknown>): string {
  // `atob` (session.ts) exige le remplissage « = » ; base64url le retire.
  const coder = (valeur: object) => Buffer.from(JSON.stringify(valeur)).toString("base64");
  return `${coder({ alg: "none", typ: "JWT" })}.${coder(claims)}.signature`;
}

function agregat(id: string, nom: string) {
  return {
    dossier_id: id,
    nom,
    tva_recettes_regime: "franchise",
    plateformes: [],
    exercice_debut: "2025-01-01",
    exercice_fin: "2025-12-31",
    ca_ht_cts: 100_00,
    charges_cts: 40_00,
    resultat_cts: 60_00,
    statut_invitation: "actif",
    mode_acces_bancaire: "gestionnaire",
    forme_juridique: "EURL",
    regime_imposition: "IS",
    regime_tva: "franchise",
    annee_courante: 2026,
    etape_courante: "Compte",
    annee_precedente: 2025,
    etape_precedente: "Compte",
    alerte_regime: null,
    alerte_tva: null,
  };
}

const DOSSIER_SOPHIE = {
  dossier_id: "DEMO_sophie",
  nom: "Sophie Martin",
  tva_recettes_regime: "franchise",
  plateformes: [],
  exercice_debut: "2025-01-01",
  exercice_fin: "2025-12-31",
  ca_ht_cts: 100_00,
  charges_cts: 40_00,
  resultat_cts: 60_00,
  tresorerie_cts: 20_00,
  tva_a_payer_cts: 0,
  nb_transactions: 1,
  nb_a_trancher: 1,
  statut_invitation: "actif",
  mode_acces_bancaire: "gestionnaire",
  peut_connecter_sa_banque: false,
  cloture_faite: false,
  greffe_inpi_signe: false,
  guide_greffe: { depose: false, lien: "", lignes: [], pieces: [] },
  declaration_resultat: "2065",
  depot_greffe: true,
  alerte_regime: null,
  regimes_a_venir: [],
  alerte_tva: null,
  paie_par_bulletin: false,
  forme_juridique: "EURL",
  regime_libelle: "Impôt sur les sociétés",
};

const ZARA = {
  ecriture_id: "zara-1",
  date: "2025-06-01",
  libelle: "ZARA",
  montant_cts: -4_200,
  compte: "471",
  statut: "à trancher",
  a_justificatif: true,
  proposition: null,
  origine_proposition: null,
  confiance_proposition: null,
};

async function bouchon(route: Route) {
  const url = route.request().url();
  const methode = route.request().method();
  if (url.endsWith("/dossiers") && methode === "GET") {
    await route.fulfill({
      json: [agregat("DEMO_karim", "Karim"), agregat("DEMO_sophie", "Sophie"), agregat("DEMO_yanis", "Yanis")],
    });
    return;
  }
  if (url.endsWith("/dossiers/DEMO_sophie") && methode === "GET") {
    await route.fulfill({ json: DOSSIER_SOPHIE });
    return;
  }
  if (url.endsWith("/transactions") && methode === "GET") {
    await route.fulfill({ json: [ZARA] });
    return;
  }
  if (url.endsWith("/decision") && methode === "POST") {
    await route.fulfill({ json: { ...ZARA, statut: "validé", compte: "455" } });
    return;
  }
  if (url.includes("/cloture-exercice") && methode === "GET") {
    await route.fulfill({
      json: {
        possible: true,
        raison: null,
        exercice_debut: "2025-01-01",
        exercice_fin: "2025-12-31",
        nouvel_exercice_debut: "2026-01-01",
        ecritures: ["Liquidation de la TVA de l'exercice"],
        changements: [],
        attestation: "J'atteste la clôture.",
      },
    });
    return;
  }
  if (url.includes("/provisions-cloture") && methode === "GET") {
    await route.fulfill({ json: { lignes: [] } });
    return;
  }
  if (url.includes("/provisions-cloture") && methode === "PUT") {
    await route.fulfill({ json: route.request().postDataJSON() });
    return;
  }
  if (url.includes("/affectation")) {
    await route.fulfill({ json: { applicable: false, raison: null } });
    return;
  }
  if (url.includes("connexions-bancaires")) {
    await route.fulfill({
      json: {
        relance_portefeuille: "auto",
        compteurs: { actif: 0, a_renouveler: 0, expire: 0, jamais_connecte: 0 },
        a_reconnecter: 0,
        dossiers: [],
      },
    });
    return;
  }
  await route.fulfill({ json: [] });
}

async function intercepterApi(page: Page) {
  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.includes(":3000") || url.startsWith("data:")) {
      await route.continue();
      return;
    }
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-headers": "*",
          "access-control-allow-methods": "*",
        },
      });
      return;
    }
    await bouchon(route);
  });
}

async function session(page: Page, cle: string, corps: object) {
  await page.addInitScript(
    ([storageKey, valeur]) => window.localStorage.setItem(storageKey, valeur),
    [cle, JSON.stringify(corps)] as const,
  );
}

test("le gestionnaire voit les trois dossiers", async ({ page }) => {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  await session(page, "axelcompta_session_gestionnaire", {
    accessToken: jeton({ exp, app_metadata: { tenant_id: "TENANT_DEMO" } }),
    refreshToken: "rafraichissement",
    tenantId: "TENANT_DEMO",
    email: "gestionnaire@example.com",
  });
  await intercepterApi(page);
  await page.goto("/portefeuille");
  await expect(page.getByRole("heading", { name: "Entreprises" })).toBeVisible();
  await expect(page.getByText("Karim")).toBeVisible();
  await expect(page.getByText("Sophie")).toBeVisible();
  await expect(page.getByText("Yanis")).toBeVisible();
});

test("Sophie saisit une facture pas encore reçue", async ({ page }) => {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  await session(page, "axelcompta_session_chauffeur", {
    accessToken: jeton({ exp, app_metadata: { dossier_id: "DEMO_sophie" } }),
    refreshToken: "rafraichissement",
    dossierId: "DEMO_sophie",
    email: "sophie@example.com",
  });
  await intercepterApi(page);
  await page.goto("/chauffeur/DEMO_sophie/exercice");
  await expect(page.getByRole("heading", { name: "Exercice", exact: true })).toBeVisible();
  await page.getByLabel("Compte de charge").fill("622");
  await page.getByLabel("Montant").fill("80");
  await page.getByLabel("Libellé").fill("honoraire de décembre");
  await page.getByRole("button", { name: "Ajouter" }).click();
  await expect(page.getByText("honoraire de décembre")).toBeVisible();
  await expect(page.getByText("Facture pas encore reçue — honoraire de décembre (622)")).toBeVisible();
});

test("Sophie tranche une dépense et l'écran suit", async ({ page }) => {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  await session(page, "axelcompta_session_chauffeur", {
    accessToken: jeton({ exp, app_metadata: { dossier_id: "DEMO_sophie" } }),
    refreshToken: "rafraichissement",
    dossierId: "DEMO_sophie",
    email: "sophie@example.com",
  });
  await intercepterApi(page);
  await page.goto("/chauffeur/DEMO_sophie");
  await expect(page.getByRole("heading", { name: "Sophie Martin" })).toBeVisible();
  await expect(page.getByText("ZARA")).toBeVisible();
  await page.getByRole("button", { name: "Personnelle" }).click();
  await expect(page.getByText("Tout est à jour.")).toBeVisible();
});
