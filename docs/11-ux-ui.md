# 11 — UX / UI : interface B2B

> **État au 2026-11-13** (ajouté ; le reste du doc décrit la cible
> d'origine) : l'hypothèse « le chauffeur ne voit que la page de signature »
> est caduque (doc 19). Écrans réels :
> - Chauffeur (mobile) : Activité, À traiter (avec les versements de
>   plateformes « à vérifier », AXE-891), Exercice (avec « Véhicule et
>   matériel » et « LOA », AXE-802 et AXE-803), Mon résultat, Ma TVA
>   (AXE-805), Ma société (siège, capital, associés, AXE-846), Reprendre mes
>   comptes (bilan d'ouverture depuis un FEC, AXE-804), Compte (« Mes
>   comptes bancaires », AXE-832 et AXE-729 ; « Mes plateformes » avec
>   Rollee Connect et les derniers versements, AXE-819 et AXE-821 ; « Accès
>   à votre dossier », AXE-812), la carte « Vérifiez votre entreprise »
>   (AXE-730, et les écarts avec les registres, AXE-849) et la cloche. Une
>   dépense sans ticket montre sa TVA estimée (AXE-831).
> - Gestionnaire : Entreprises (tags, AXE-829 ; nouveaux chauffeurs
>   Digifactory et « Synchroniser », AXE-845 ; comptes à choisir, AXE-851 ;
>   comptes Rollee à choisir et filtre Rollee, AXE-911 ; écarts avec les
>   registres, AXE-849), Importer des entreprises (AXE-809), Invitations,
>   Rappels (suivi des envois, AXE-808 ; « plateformes non reliées »,
>   AXE-890), Équipe (habilitation de l'expert, réinitialisation de la MFA),
>   Intégrations (plusieurs accès par type : Digifactory, e-mail, SMS,
>   Rollee, avec Tester, AXE-872 ; activité de l'IA en nombre de libellés,
>   AXE-887), Mode expert (engagement, motifs, opérations classées, bilan
>   d'ouverture, AXE-800, AXE-823, AXE-804) et Anomalies (historique,
>   opérations bancaires à revoir, AXE-814 et AXE-424).
> - Écran « Double authentification » à la connexion (AXE-812) ; bandeau
>   « Mode test, lecture seule » du compte de test (AXE-822) ; textes
>   juridiques publics sur `/legal/…` (AXE-859).
> - Le design system est [DESIGN.md](../DESIGN.md), passé en v2.0 le
>   2026-11-11 (refonte AXE-873, direction C2,
>   [ADR-008](adr/ADR-008-design-system-monochrome.md)) : monochrome à
>   l'encre, un accent orange foncé, navigation en barre latérale claire,
>   tous les écrans repris (PR #137 à #151).
> - Les revues UX d'Arthur (AXE-563, AXE-564) ont été traitées le 04/11 et
>   le 05/11.

> Statut : brouillon à valider — Dernière mise à jour : 2026-06-16
>
> **⚠️ Révisé le 2026-09-11 (doc 19)** : ce doc a été écrit avant la
> décision du 2026-09-11 sur qui voit quoi. **La file de revue (§3.1),
> l'instruction d'alerte (§3.2) et la clôture (§2, listée dans l'arbre
> portefeuille) ne sont plus des écrans gestionnaire — ce sont des écrans
> indiv** (doc 19 §5). Les patterns d'interaction décrits ici (raccourcis
> clavier, présentation d'une transaction, ton neutre) restent valables
> tels quels — c'est le **propriétaire de l'écran** qui change, pas
> l'écran. La page de signature (§3.3) était déjà correcte dans son
> principe (« chauffeur/gérant »), juste incomplète (doc 19 en fait un
> parcours complet, pas un écran isolé). Lire doc 19 avant de construire
> quoi que ce soit depuis ce doc.

> **Design system** : tous les tokens (couleurs, typo, spacing, composants,
> breakpoints) sont dans [`DESIGN.md`](../DESIGN.md) à la racine du projet.
> Ce document décrit l'intention et les patterns UX ; `DESIGN.md` est la
> référence d'implémentation. En cas de conflit, `DESIGN.md` fait foi.

## 1. Intention

Référence exprimée : la sobriété et la finition « à la Apple ». Traduction pour un
outil B2B de production comptable :

- **Clarté avant densité.** Beaucoup d'outils comptables affichent tout, tout le
  temps. Nous affichons *ce qui demande une décision*, le reste est accessible mais
  en retrait.
- **Calme visuel.** Fond blanc cassé, blancs généreux, texte et bouton
  principal à l'encre, une seule couleur d'accent (orange foncé, ADR-008),
  Inter seule, coins arrondis discrets, cartes cernées d'un filet plutôt que
  d'une ombre, micro-transitions sobres (150-200 ms). Mode sombre en phase 5.
- **La hiérarchie suit le flux de travail**, pas la structure de la base de données.
- **Chiffres irréprochables** : alignement tabulaire des montants (chiffres à
  chasse fixe), format français (`1 234,56 €`), négatifs visuellement distincts.
- Accessibilité : contrastes AA, navigation clavier complète (les pros vivent au
  clavier), focus visibles.

## 1bis. Une UI qui s'adapte : 1 vs 200 dossiers, et au statut de chaque dossier

Deux axes d'adaptation, prévus dès la conception même si le mode mono arrive après
le pilote :

**Axe 1 — Le mode du tenant (portefeuille vs mono-entreprise).** Le principe :
le mode mono-entreprise est le mode portefeuille **sans la couche portefeuille**.
La fiche dossier, les transactions, la revue, la clôture sont les mêmes écrans.
Concrètement :

| Élément | Mode portefeuille (200 dossiers) | Mode mono-entreprise (1 dossier) |
|---------|----------------------------------|----------------------------------|
| Accueil | Santé du portefeuille, dossiers en retard | Directement le tableau de bord DU dossier |
| Navigation | Tenant → liste des dossiers → fiche | La fiche dossier EST la navigation racine |
| File de revue | Transversale, tous dossiers, priorisée | Celle du dossier unique |
| Vocabulaire | « Entreprises » (écran gestionnaire, 2026-09-25). « Chauffeur » reste le nom technique des routes indiv. | « Votre comptabilité » |

Règle d'implémentation : aucun composant d'écran de niveau dossier ne doit
connaître l'existence du portefeuille (il reçoit un `dossier_id`, point). La couche
portefeuille est un habillage au-dessus. C'est ce qui garantit qu'activer le mode
mono plus tard = construire un habillage léger, pas refondre.

**Axe 2 — Le statut/régime du dossier.** L'UI lit la configuration du dossier
(doc 06 §7) et n'affiche que ce qui existe pour lui : un dossier à l'IS montre
« IS et liasse 2050 », un dossier à l'IR montre « 2031 », un futur dossier micro
n'aurait ni module liasse ni grand livre mais un livre des recettes et une jauge de
seuils. Les modules s'activent par configuration — pas de pages grisées ni de
fonctions qui « ne marchent pas pour ce dossier ».

## 2. Architecture de l'information (mode portefeuille, V1)

> **Périmètre gestionnaire réduit depuis le 2026-09-11 (doc 19 §2.1/§2.4)** :
> l'arbre ci-dessous mélange encore écrans gestionnaire et écrans indiv tels
> qu'imaginés au 2026-06-16. Côté **gestionnaire**, ne restent que : santé
> du portefeuille (agrégats), statut d'onboarding des indivs, santé des
> connexions bancaires **si légalement affichable** (doc 02 §10). Tout le
> reste de l'arbre — dossier en détail, transactions, justificatifs,
> comptabilité, clôture, file de revue, alertes, documents & signatures —
> est **côté indiv** (doc 19 §5). Arbre laissé tel quel ci-dessous comme
> inventaire des écrans à répartir, pas comme plan d'IA gestionnaire.

```text
├── Tableau de bord (par tenant)
│   ├── Santé du portefeuille : dossiers à jour / en retard / bloqués
│   ├── À traiter : revues en attente, alertes ouvertes, pièces manquantes
│   └── Santé des connexions bancaires (consentements à renouveler)
├── Dossiers (liste → fiche dossier)
│   ├── Vue d'ensemble : solde, complétude, prochaine échéance
│   ├── Transactions (filtres : à valider / alertes / sans pièce)
│   ├── Justificatifs (matching, orphelins)
│   ├── Comptabilité : journaux, grand livre, balance (lecture experte)
│   ├── Immobilisations & contrats (LOA)
│   └── Clôture : checklist guidée, états, liasse
├── File de revue (transversale, le « cockpit » quotidien)
├── Alertes & anomalies (instruction, historique)
├── Documents & signatures (paquets envoyés, statuts)
└── Paramètres (tenant, dossiers, règles, profils d'import, utilisateurs)
```

## 3. Les trois écrans qui font le produit

> **Les trois, désormais côté indiv (doc 19 §5), pas gestionnaire** —
> notamment §3.1/§3.2 déclenchées par notification au fil de l'eau, pas
> en session de revue groupée (doc 19 §5.2).

### 3.1 La file de revue (l'écran le plus utilisé)

Objectif : **< 10 secondes par décision**.

- Une transaction à la fois, en pleine largeur : libellé brut, montant, date,
  justificatif côte à côte s'il existe, proposition avec **source et explication**
  (« règle X » / « ML 0,87 » / « LLM : ... »), top-3 alternatives.
- Clavier : `A` accepter, `1-3` choisir une alternative, `R` rechercher une
  catégorie, `S` passer, `J` joindre une pièce. Lot suivant automatique.
- Après 3 corrections identiques : proposition contextuelle de créer une règle
  (« Toujours classer SHELL AUTOROUTE en carburant pour ce dossier ? »).

### 3.2 L'instruction d'alerte

- L'alerte présentée comme un dossier à instruire : transaction, détecteur
  déclenché, **écart au profil comportemental du dossier** (« d'habitude : 45-70 €
  de carburant, 2×/semaine — ici : 92 €, 3e fois cette semaine »), historique sur
  cette enseigne, ticket s'il existe.
- Trois issues claires : « Justifié » (commentaire/pièce), « Usage personnel »
  (déclenche le template comptable, doc 06 §3.6), « Faux positif » (nourrit le ML).
- Ton neutre dans toute l'UI : « à justifier », jamais « fraude » (doc 05 §6.1).

### 3.3 La page de signature (seul écran vu par le chauffeur/gérant)

- Accès par lien, zéro création de compte, OTP email, **mobile d'abord** (le
  chauffeur est dans sa voiture).
- Les documents présentés avec un résumé en langage clair au-dessus du PDF :
  « Votre résultat 2025 : … ; vous signez : bilan, liasse, PV » — relecture
  possible page par page, puis signature (prestataire eIDAS intégré).
- Suivi côté B2B : envoyé / ouvert / lu / signé / relancé, avec relances
  automatiques paramétrables.

## 4. Patterns transverses

| Pattern | Règle |
|---------|-------|
| États vides | Toujours une action (« Importer votre premier fichier »), jamais une page blanche. |
| Chargements | Squelettes, jamais de spinner plein écran. |
| Erreurs | Langage humain + action de récupération ; jamais un code brut. |
| Destructif | Confirmation explicite ; rien de destructif sur les faits comptables de toute façon (append-only). |
| Traçabilité visible | Sur chaque écriture : « qui, quand, pourquoi » à un clic (doc 05 §7) — la confiance se voit. |
| Badges de statut | Un seul vocabulaire : proposé / validé / clôturé ; ouvert / instruit ; pièce manquante / matchée. |
| Recherche globale | `⌘K` : dossiers, transactions, comptes, écrans. |

## 5. Implémentation

- **Next.js + TypeScript strict** (doc 03), composants sur base **Radix UI +
  Tailwind** (shadcn/ui comme point de départ, tokens personnalisés selon
  `DESIGN.md` — voir section correspondance Tailwind/shadcn de ce fichier).
- Tableaux virtualisés (TanStack Table + Virtual) pour les journaux/grand livre.
- Page de signature : SSR, payload minimal, cible < 1 s de premier rendu en 4G.
- Storybook publié = catalogue vivant du design system ; tests visuels de
  régression (Chromatic ou Playwright screenshots) sur les composants clés.

### Règles d'implémentation issues de `DESIGN.md`

- Tout montant = token `amount-*` + `tabular-nums` + `text-right`. Sans exception.
- Fond body = `canvas-app` (`#FBFAF8`), jamais `#FFFFFF` directement.
- Un seul accent : l'orange foncé `signal` (`#C2410C`), pour les repères, les
  liens d'action et le focus ; le bouton principal est à l'encre (`#111111`),
  jamais orange ; au plus un surlignage jaune par écran. Pas de deuxième
  couleur de marque sans ADR (ADR-008, qui remplace l'accent bleu d'origine).
- Transitions à 150 ms max. Pas de spinner plein écran — squelettes uniquement.
- Pas de page grisée : les modules non applicables au dossier sont absents, pas
  désactivés.

## 6. Validation UX prévue au planning

- Maquettes Figma des trois écrans clés (§3) **avant** de coder le front.
- Test utilisateur réel : 2-3 personnes du client gestionnaire sur les maquettes, puis
  sur staging — prévu dans la roadmap (doc 12, jalon M2), pas en option.
- L'A/B testing produit du lancement (mentionné au cadrage) portera d'abord sur la
  file de revue (variantes de seuils d'auto-validation et de présentation des
  explications).
