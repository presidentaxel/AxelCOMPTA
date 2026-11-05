# ADR-004 — Prestataire de signature électronique : Yousign (pressenti)

**Date :** 2026-06-16
**Statut :** en attente de devis — décision de périmètre prévue en décembre 2026 (AXE-441, sous AXE-770)
**Décideurs :** Louis Vedovato

> **Mise à jour 2026-09-11 (doc 20 §4/§6)** : le dépôt des comptes annuels
> au greffe (Guichet Unique INPI) exige spécifiquement une **signature
> électronique qualifiée (QES) avec certificat RGS** (C. com. art.
> R.123-5) — pas seulement le niveau « avancé eIDAS » évalué ci-dessous.
> **Yousign a été rebrandé Youtrust en 2026** (`developers.yousign.com`
> redirige vers `developers.youtrust.com`). Écart trouvé : leur doc
> développeur indique explicitement **« QES cannot be embedded »** — le
> candidat pressenti ci-dessous ne couvre pas ce cas d'usage précis en
> restant dans notre app, contrairement à l'hypothèse implicite de ce
> document. Comparatif complet, avec **Universign** (QES embarquable en
> iframe d'après leur doc) et **CertEurope/Certigreffe** (certificat
> individuel par dirigeant, hors de notre app) : [doc 20 §6](../20-integration-inpi-depot-comptes.md#6-comparatif-prestataires-signature-qualifiée-rgs-recherche-2026-09-11).
> **Tranché par Louis (2026-09-11) : AxeLCompta ne signera jamais comme
> mandataire, quel que soit le gain UX/coût.** Signer engagerait la
> responsabilité d'AxeLCompta sur le dépôt — contraire à la décision
> structurante n°1 du projet (doc 02 §2.3 : AxeL ne tient jamais la
> comptabilité/les actes en son nom, l'utilisateur professionnel valide
> tout). **Sujet clos, ne pas rouvrir.** Chaque dirigeant/dossier doit donc
> obtenir et utiliser son propre certificat qualifié — ~200 signataires
> individuels en V1, jamais un seul certificat côté AxeLCompta. Ça renforce
> l'intérêt d'un prestataire dont le parcours QES individuel reste
> embarquable dans notre app (Universign) plutôt qu'un qui renvoie chaque
> utilisateur ailleurs (Yousign/Youtrust pour la QES, CertEurope).
>
> **Précisé le 2026-09-11 (doc 20 §4bis, doc 19 §5.3) : cet ADR ne couvre
> que la seconde des deux signatures du parcours de clôture — la
> légale.** Il existe une première signature (l'indiv valide les comptes
> avant tout envoi, nous protège nous) qui n'a pas besoin d'un niveau
> eIDAS qualifié et ne dépend donc pas forcément de ce choix de
> prestataire — peut rester une confirmation interne simple. Ne pas
> présumer qu'un seul prestataire/une seule intégration couvre les deux.

## Contexte

Le circuit de validation finale (doc 11 §3.3, doc 19 §5.3) nécessite une signature électronique qualifiée ou avancée eIDAS pour les liasses fiscales et bilans. La signature est déclenchée côté AxeLCompta et réalisée par le gérant du dossier (chauffeur) sur une page mobile-first sans création de compte.

## Contraintes

- **Parcours sans compte** : le signataire accède via un lien OTP email, sans s'inscrire.
- **Mobile-first** : les chauffeurs signent depuis leur téléphone.
- **API propre** : l'intégration doit être pilotable programmatiquement (génération de liens, webhooks sur événements de signature, archivage des preuves).
- **eIDAS** : niveau avancé (simple suffisant pour nos documents, qualifié si exigé par le client).
- **Hébergement France/UE** : cohérent avec ADR-003.

## Candidats évalués

| Critère | Yousign | Docusign |
|---------|---------|---------|
| Société française | ✅ | ❌ (US) |
| API REST moderne | ✅ | ✅ |
| Parcours sans compte | ✅ | ✅ |
| Pricing (petits volumes) | ✅ Abordable | ⚠️ Élevé |
| eIDAS avancé | ✅ | ✅ |
| Archivage preuve inclus | ✅ | ✅ |

## Décision provisoire

**Yousign** est le candidat principal. Société française, API propre, pricing adapté aux volumes V1 (~200 signatures/an en démarrage). À confirmer par un devis et une POC de l'intégration en phase 0.

## Action requise

- [ ] Demander un devis Yousign (volume estimé : 200-400 signatures/an en V1)
- [ ] POC : générer un lien de signature, capter le webhook "signé", récupérer le document signé avec sa preuve
- [ ] Vérifier que le client pilote n'a pas de prestataire imposé
