import { expect, test, type Page, type Route } from "@playwright/test";

/** Même chiffre, même libellé, sur Activité, Exercice et Mon résultat.
 * L'affectation renvoie un autre montant pour prouver qu'il n'est pas affiché. */

function jeton(claims: Record<string, unknown>): string {
  const coder = (valeur: object) => Buffer.from(JSON.stringify(valeur)).toString("base64");
  return `${coder({ alg: "none", typ: "JWT" })}.${coder(claims)}.signature`;
}

const DOSSIER = {
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
  nb_a_trancher: 0,
  statut_invitation: "actif",
  mode_acces_bancaire: "gestionnaire",
  peut_connecter_sa_banque: false,
  cloture_faite: true,
  greffe_inpi_signe: false,
  guide_greffe: { depose: false, lien: "", lignes: [], pieces: [] },
  declaration_resultat: "2065",
  depot_greffe: false,
  alerte_regime: null,
  regimes_a_venir: [],
  alerte_tva: null,
  paie_par_bulletin: false,
  forme_juridique: "EURL",
  regime_libelle: "Impôt sur les sociétés",
};

const SCENARIO = {
  cle: "garder",
  libelle: "Tout garder dans la société",
  dividendes_cts: 0,
  impot_revenu_cts: 0,
  prelevements_sociaux_cts: 0,
  part_soumise_cotisations_cts: 0,
  net_percu_cts: 0,
  laisse_en_societe_cts: 50_00,
  tresorerie_apres_cts: 40_00,
};

const AFFECTATION = {
  applicable: true,
  raison: null,
  annee_exercice: 2025,
  resultat_cts: 123_456,
  reserve_legale_cts: 10_00,
  distribuable_cts: 50_00,
  disponible_cts: 40_00,
  scenarios: [SCENARIO],
  avertissements: [],
};

async function bouchon(route: Route) {
  const url = route.request().url();
  const methode = route.request().method();
  if (url.endsWith("/dossiers/DEMO_sophie") && methode === "GET") {
    await route.fulfill({ json: DOSSIER });
    return;
  }
  if (url.includes("/affectation") && methode === "POST") {
    await route.fulfill({
      json: { applicable: false, raison: "Résultat 2025 affecté.", annee_exercice: 2025 },
    });
    return;
  }
  if (url.includes("/affectation") && methode === "GET") {
    await route.fulfill({ json: AFFECTATION });
    return;
  }
  if (url.includes("/cloture-exercice") && methode === "GET") {
    await route.fulfill({
      json: {
        possible: false,
        raison: "Exercice clos.",
        exercice_debut: "2026-01-01",
        exercice_fin: "2026-12-31",
        nouvel_exercice_debut: null,
        ecritures: [],
        changements: [],
        attestation: null,
      },
    });
    return;
  }
  if (url.includes("/transactions") && methode === "GET") {
    await route.fulfill({
      json: [
        {
          ecriture_id: "course-1",
          date: "2025-06-01",
          libelle: "UBER",
          montant_cts: 2_500,
          compte: "706",
          statut: "validé",
          a_justificatif: false,
          proposition: null,
          origine_proposition: null,
          confiance_proposition: null,
        },
      ],
    });
    return;
  }
  if (url.includes("/provisions-cloture")) {
    await route.fulfill({ json: methode === "GET" ? { lignes: [] } : route.request().postDataJSON() });
    return;
  }
  await route.fulfill({ json: [] });
}

async function ouvrir(page: Page, chemin: string) {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  await page.addInitScript(
    ([cle, valeur]) => window.localStorage.setItem(cle, valeur),
    [
      "axelcompta_session_chauffeur",
      JSON.stringify({
        accessToken: jeton({ exp, app_metadata: { dossier_id: "DEMO_sophie" } }),
        refreshToken: "rafraichissement",
        dossierId: "DEMO_sophie",
        email: "sophie@example.com",
      }),
    ] as const,
  );
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
  await page.goto(chemin);
}

function dateDuJour(): string {
  const date = new Date();
  const jour = String(date.getDate()).padStart(2, "0");
  const mois = String(date.getMonth() + 1).padStart(2, "0");
  return `${jour}/${mois}/${date.getFullYear()}`;
}

test.use({ viewport: { width: 375, height: 812 } });

test("les trois écrans affichent le même résultat à ce jour", async ({ page }) => {
  const libelle = `Résultat à ce jour, ${dateDuJour()}`;
  await ouvrir(page, "/chauffeur/DEMO_sophie");
  await expect(page.getByText(libelle)).toBeVisible();
  await expect(page.getByText("Résultat de l'exercice")).toHaveCount(0);
  const activite = page.getByText(libelle).locator("xpath=..");
  await expect(activite).toContainText("60,00");
  await page.screenshot({
    path: "/opt/cursor/artifacts/activite-resultat.png",
    fullPage: false,
  });

  await page.goto("/chauffeur/DEMO_sophie/exercice");
  await expect(page.getByRole("heading", { name: "Exercice", exact: true })).toBeVisible();
  await expect(page.getByText(libelle)).toBeVisible();
  await expect(page.getByText("Résultat", { exact: true })).toHaveCount(0);
  const exercice = page.getByText(libelle).locator("xpath=..");
  await expect(exercice).toContainText("60,00");
  await page.screenshot({
    path: "/opt/cursor/artifacts/exercice-resultat.png",
    fullPage: false,
  });

  await page.goto("/chauffeur/DEMO_sophie/resultat");
  await expect(page.getByRole("heading", { name: "Mon résultat 2025" })).toBeVisible();
  await expect(page.getByText(libelle)).toBeVisible();
  const resultat = page.getByText(libelle).locator("xpath=..");
  await expect(resultat).toContainText("60,00");
  await expect(page.getByText("234,56")).toHaveCount(0);
  await page.screenshot({
    path: "/opt/cursor/artifacts/resultat-montant.png",
    fullPage: false,
  });
});

test("le montant libre refuse le vide et accepte 1 000,50", async ({ page }) => {
  await ouvrir(page, "/chauffeur/DEMO_sophie/resultat");
  await expect(page.getByRole("heading", { name: "Mon résultat 2025" })).toBeVisible();

  const radios = page.locator('input[type="radio"]');
  await expect(radios).toHaveCount(2);
  await expect(radios.nth(0)).toHaveAttribute("name", "scenario");
  await expect(radios.nth(1)).toHaveAttribute("name", "scenario");

  const champ = page.getByRole("textbox", { name: "Montant (€)" });
  await expect(page.getByText("Montant (€)", { exact: true })).toBeVisible();
  await expect(champ).toBeVisible();
  expect(await champ.evaluate((el) => getComputedStyle(el).fontSize)).toBe("16px");

  const message = page.locator("#montant-dividendes-message");
  await page.getByRole("radio", { name: "Un autre montant de dividendes" }).check();
  await expect(message).toHaveText("Indiquez un montant.");
  const bouton = page.getByRole("button", { name: "Enregistrer ma décision" });
  await expect(bouton).toBeDisabled();
  await page.screenshot({
    path: "/opt/cursor/artifacts/montant-vide.png",
    fullPage: true,
  });

  await champ.fill("1 000,50");
  await expect(message).toHaveCount(0);
  await page.getByRole("checkbox").check();
  await expect(bouton).toBeEnabled();

  await champ.fill("1\u00a0000,50");
  await expect(bouton).toBeEnabled();
  await champ.fill("1\u202f000,50");
  await expect(bouton).toBeEnabled();
  await expect(message).toHaveCount(0);

  await champ.fill("");
  await expect(message).toHaveText("Indiquez un montant.");
  await expect(bouton).toBeDisabled();

  await champ.fill("1 000,50");
  await expect(bouton).toBeEnabled();
  await page.screenshot({
    path: "/opt/cursor/artifacts/montant-valide.png",
    fullPage: true,
  });

  const [requete] = await Promise.all([
    page.waitForRequest((demande) => demande.url().includes("/affectation") && demande.method() === "POST"),
    bouton.click(),
  ]);
  expect(requete.postDataJSON()).toEqual({ scenario: "libre", dividendes_cts: 100_050 });
  await expect(page.getByText("Résultat 2025 affecté.")).toBeVisible();
});
