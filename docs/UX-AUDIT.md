# Étude UX — PDF Studio et iLovePDF

Date : 6 octobre 2026. Version auditée : commit `d029cce`.

## Conclusion

PDF Studio reprend des éléments visuels d’iLovePDF, mais son parcours n’est pas encore cohérent. Le problème principal est la confiance : un bouton peut promettre une action différente de celle exécutée, la navigation modifie la sélection, et la sortie attendue n’est pas suffisamment expliquée.

Le catalogue contient **28 cartes, dont 6 reliées à un traitement**. Les 22 autres annoncent « Coming soon ». Les six traitements présents ne constituent pas une équivalence fonctionnelle complète avec les outils correspondants d’iLovePDF : « Organize PDF » ne fait que supprimer des pages, par exemple.

**Priorité : rendre prévisible le parcours choisir → importer → configurer → traiter → récupérer → continuer.** L’ajout de cartes et le polissage des couleurs passent après cette cohérence.

Cette livraison est une étude et un cahier de corrections. Les problèmes décrits ci-dessous ne sont pas encore corrigés par ce commit.

## Méthode et limites

- Consultation des pages officielles Merge, Split, Compress et du guide d’iLovePDF.
- Observation en navigateur de l’écran initial Split ; comparaison avec les captures fournies pour les états après import.
- Lecture du code de PDF Studio, y compris les traitements et les tests existants.
- Reproduction locale de sept anomalies avec des PDF synthétiques de trois pages. Résultats dans `ux-baseline.json`, script dans `reproduce_ux_baseline.py`.
- Aucun document personnel envoyé à iLovePDF. Aucun test de téléchargement, compte, paiement, Smart Split ou cloud effectué sur le site.
- Il s’agit d’un audit expert et de vérifications techniques, pas d’une étude avec des utilisateurs recrutés. Les recommandations ne sont pas présentées comme des mesures de satisfaction.

## Ce qu’il faut reprendre de la référence

La page initiale donne une tâche et une action principale. Les réglages apparaissent après l’import. Merge explique comment réordonner les fichiers et demande davantage de fichiers lorsque nécessaire. [Page Merge](https://www.ilovepdf.com/merge_pdf)

Split distingue plage personnalisée, découpage fixe et extraction de pages. Le choix de regrouper les sorties est explicite. [Page Split](https://www.ilovepdf.com/split_pdf)

Compress présente trois compromis qualité/taille. Son unité de travail est le fichier. [Page Compress](https://www.ilovepdf.com/compress_pdf)

Organize permet de réordonner et supprimer ; Remove Pages est une tâche distincte. Le guide décrit aussi les réglages d’orientation et de marges pour JPG to PDF. [Guide officiel](https://www.ilovepdf.com/help/documentation)

Les détails ci-dessous sont nos décisions proposées pour l’application desktop, et non des comportements tous vérifiés sur le site : conservation des sessions par outil, retour explicite, annulation locale, traitement en temporaire puis enregistrement.

## Diagnostic priorisé

P1 = erreur de tâche, perte de sélection, ambiguïté de résultat ou récupération bloquée. P2 = friction importante. P3 = confort. « Reproduit » signifie exécuté avec les fixtures ; « code » signifie établi par lecture ; « référence » indique une différence de capacité.

| ID | Priorité / preuve | Problème actuel | Effet pour l’utilisateur | Correction et critère de réussite |
|---|---|---|---|---|
| U01 | P1 · reproduit | Merge avec A+B → Compress → Merge ne conserve que A. | La sélection est perdue sans décision explicite. Les originaux sur disque restent intacts. | Chaque outil conserve sa session. Revenir dans Merge retrouve A+B et leur ordre. |
| U02 | P1 · reproduit | Cliquer de nouveau sur Split remet la plage 2–2 à 1–3. | Le travail disparaît en cliquant un onglet déjà actif. | Outil actif = aucune remise à zéro ; « Nouvelle tâche » est une action distincte. |
| U03 | P1 · reproduit | Le sélecteur accepte deux PDF pour Compress, mais seul le premier est gardé. | Un fichier choisi est ignoré silencieusement. | Supporter le lot ou imposer un sélecteur mono-fichier explicite. À terme, compression par lot. |
| U04 | P1 · code | « Add files » remplace le fichier dans Split/Compress/Rotate/Delete. | Le libellé promet un ajout et provoque un remplacement. | « Ajouter des fichiers » pour un lot ; « Remplacer le PDF » pour une tâche mono-fichier. |
| U05 | P1 · reproduit | Un PDF invalide dans Merge annule tout le chargement ; aucune carte n’apparaît. | Impossible de retirer le fichier défectueux via sa carte. | Conserver les cartes valides et afficher l’erreur sur la carte invalide avec Retirer/Remplacer. |
| U06 | P1 · code + référence | « Organize PDF » ouvre « Delete pages ». | Réordonner n’est pas disponible malgré le nom de l’outil. | Implémenter l’ordre des pages, suppression, restauration et aperçu ; proposer Remove Pages séparément. |
| U07 | P1 · reproduit | Cliquer une miniature en mode Ranges bascule automatiquement vers Pages. | Un geste d’inspection change la méthode de découpage. | Changement de mode uniquement via les onglets ; aperçu via un contrôle dédié. |
| U08 | P1 · reproduit | Plage 3–1 : bouton Split actif ; erreur seulement après clic, dans le footer. | L’interface laisse lancer une configuration invalide. | Validation au niveau du champ ; erreur lisible ; action désactivée tant que la plage est invalide. |
| U09 | P1 · reproduit | Combiner 1–2 et 2–3 donne trois pages, car la page 2 est dédupliquée. | La sortie ne correspond pas à la concaténation des plages affichées. | Définir explicitement le contrat : conserver 1,2,2,3, ou avertir du chevauchement. Aucune déduplication silencieuse. |
| U10 | P1 · code | En extraction Pages, la sortie est toujours un PDF ; l’option de regroupement ne s’applique qu’aux plages. | Le modèle mental change selon l’onglet sans explication. | Même choix partout : un PDF regroupé ou des PDF séparés ; annoncer nombre et format avant traitement. |
| U11 | P1 · code | Compress est décrit comme « lossless », mais les images peuvent être recompressées avec pertes. | L’utilisateur ne peut pas choisir correctement la qualité. | Corriger le texte ; afficher niveau et compromis ; préserver les originaux. |
| U12 | P2 · code | 22 cartes non opérationnelles ont la même apparence interactive que les six autres. | Les catégories conduisent souvent à des impasses. | Mettre les outils utilisables en avant ; disponibilité visible avant clic ; aucun faux parcours de traitement. |
| U13 | P2 · code | Convert et All tools ressemblent à des menus mais ouvrent des filtres de l’accueil. | Le résultat de l’action est peu prévisible. | Menus réels groupés, accessibles au clavier, ou libellés annonçant le retour au catalogue. |
| U14 | P2 · code | Merge utilise uniquement des flèches et aucun ordre numéroté explicite. | Réorganiser de nombreux fichiers est laborieux. | Drag-and-drop, positions visibles, tri A–Z/Z–A et flèches accessibles au clavier. |
| U15 | P2 · code | Compress affiche les pages et dit de cliquer pour les sélectionner, mais le clic ne fait rien. | Une interaction est promise sans effet. | Une carte par PDF, taille et pages ; aucun message de sélection de pages dans Compress. |
| U16 | P2 · code | Delete et Rotate n’affichent qu’une bordure rouge, comme une sélection générique. | La conséquence de l’action est difficile à prévoir. | Croix « sera supprimée » avec restauration pour Delete ; rotation visible et angle par page pour Rotate. |
| U17 | P2 · code | Aucun glisser-déposer de fichiers depuis l’Explorateur. | Le geste d’import attendu dans cette famille d’outils est absent. | Zone de dépôt réelle, validation du type et résultat identique à l’import par bouton. |
| U18 | P2 · code | Boîte Enregistrer avant traitement, puis petite fenêtre Done sans continuation. | L’utilisateur quitte sa tâche avant d’en voir le résultat et doit réimporter pour enchaîner. | Traiter vers un résultat temporaire ; écran résultat avec Enregistrer, Ouvrir, dossier, continuer et nouvelle tâche. |
| U19 | P2 · code | Compression : aucune taille avant/après ni indication quand aucune réduction n’est obtenue. | « Done » ne prouve pas que l’objectif est atteint. | Afficher octets/Ko/Mo, pourcentage et « déjà optimisé » si identique. |
| U20 | P2 · code | Erreurs dans le footer, progression indéterminée, aucune annulation réelle. | État, problème et action de récupération sont séparés. | Zone d’état près du bouton ; étape courante ; erreur actionnable ; annulation sûre sans fichier final partiel. |
| U21 | P2 · code | Cartes sans navigation clavier ; molette globale liée à la galerie cachée ; quatre colonnes fixes. | Accueil moins accessible et fragile sur petite fenêtre. | Cartes focalisables ; Entrée/Espace ; scroll sur la zone survolée ; 2–4 colonnes suivant la largeur. |
| U22 | P2 · référence | Split fixe, extraction séparée, réglages JPG, lots Compress et vrai Organize manquent. | Les parcours les plus proches du besoin ne sont pas complets. | Livrer les capacités selon la matrice et les critères ci-dessous ; les distinguer des bugs. |

## Parcours cible commun

1. **Choix de l’outil.** Nom, objectif, capacité disponible. Revenir à l’accueil conserve la tâche en cours.
2. **Import.** Bouton principal et zone de dépôt. Formats et cardinalité annoncés. L’utilisateur peut annuler le sélecteur sans rien perdre.
3. **Vérification.** Carte par fichier ou page selon la tâche. Nom, ordre, taille, nombre de pages, suppression/remplacement et erreurs locales.
4. **Configuration.** Valeurs par défaut utiles ; options adaptées à l’outil ; aperçu de l’effet ; erreurs à côté des champs.
5. **Traitement.** Un bouton principal nommé par son action. Les données sont figées pendant le travail. Progression et annulation cohérentes.
6. **Résultat.** Nombre de fichiers/pages, format et taille. Enregistrer devient l’action principale. Un échec d’enregistrement ne détruit pas le résultat temporaire.
7. **Suite.** Ouvrir, afficher le dossier, utiliser le résultat dans un autre outil, modifier les réglages ou commencer une nouvelle tâche.

Fermer avec un résultat non enregistré doit permettre d’enregistrer ou d’abandonner explicitement. Un bouton retour ne doit pas fonctionner comme une suppression implicite. Chaque modification d’ordre ou de suppression doit pouvoir être annulée.

## Contrat de chaque outil prioritaire

| Outil | Entrée / interaction | Sortie annoncée et vérifiable |
|---|---|---|
| Merge | Plusieurs PDF, minimum deux ; ordre visible et réversible ; ajout et retrait sans perdre le lot. | Un PDF dans l’ordre affiché, somme des pages des entrées. |
| Split — Custom | Un PDF ; plages numérotées avec début/fin et aperçu ; chevauchements explicités. | Un PDF regroupé ou un fichier par plage, nombre annoncé. Un seul résultat peut être enregistré directement en PDF. |
| Split — Fixed | Un PDF ; N pages par fichier, reste dans le dernier fichier. | Pour 7 pages et N=3 : 3 PDF de 3, 3 et 1 pages. |
| Split — Pages | Un PDF ; Toutes/Choisir ; miniatures et saisie « 1,3–5 » synchronisées. | Un PDF regroupé ou un fichier par page sélectionnée, selon le choix affiché. |
| Compress | Un ou plusieurs PDF ; carte par fichier ; niveau recommandé par défaut. | PDF par entrée ; lot dans une archive si nécessaire ; taille avant/après et gain réel. |
| Organize | Miniatures réordonnables, retirer/restaurer, rotation, annuler. | Ordre, pages conservées et rotations exactement conformes à l’aperçu. |
| Remove Pages | Cliquer marque la suppression ; compte des pages restantes ; restaurer possible. | Impossible de supprimer toutes les pages ; aperçu clair des pages retirées. |
| Rotate | Rotation visible ; action par page et « appliquer à toutes ». | Orientation du résultat identique à la miniature ; aucune ambiguïté sur les pages concernées. |
| JPG/images to PDF | Images réordonnables ; orientation, format de page et marges. | PDF conforme à l’ordre et aux réglages, aperçu avant traitement. |

Word, PowerPoint, Excel, OCR, édition, signature et intelligence PDF demandent chacun une spécification fonctionnelle et un moteur adaptés. Un simple bouton supplémentaire n’en livre pas l’expérience. Ils restent des capacités à développer, distinctes de la correction du parcours actuel.

## Organisation technique proposée

- Une session indépendante par outil : fichiers, ordre, pages, plages, options et résultat. L’interface reflète cette session et ne la recrée pas à chaque affichage.
- États explicites : vide, chargement, prêt, configuration invalide, traitement, résultat, erreur. Les contrôles dépendent de cet état.
- Un objet d’entrée par fichier, avec statut et erreur propres, pour ne pas bloquer les autres entrées.
- Une description de sortie calculée avant traitement : format, quantité et ordre. Le moteur doit respecter ce contrat.
- Résultat temporaire géré par la session puis copie atomique à l’enregistrement. Original jamais remplacé implicitement.
- Tester les transitions utilisateur en plus des fonctions PDF. Les tests actuels valident plusieurs traitements mais acceptent aussi le changement automatique de mode Split : passer les tests actuels ne prouve donc pas une bonne UX.

## Ordre des lots

**Lot 1 — cohérence et récupération.** U01–U11, messages locaux, libellés exacts, état par outil, erreurs par fichier. Critère : aucun fichier choisi ignoré silencieusement ; aucun changement de mode ou de sélection sans action explicite ; sortie annoncée conforme.

**Lot 2 — parcours complet des outils courants.** Drag-and-drop, réorganisation, Split fixe et Pages, vrai Organize, lots Compress, réglages images, résultat et continuation. Critère : chacun des neuf parcours du tableau se termine sans réimport inutile.

**Lot 3 — navigation et accessibilité.** Menus, accueil honnête, clavier, scroll, redimensionnement. Critère : finir Merge et Split au clavier, aucune action principale masquée à 1060×680, import et erreur accessibles.

**Lot 4 — extension de capacités.** Conversion Office, OCR, édition, signature, sécurité et intelligence, outil par outil avec critères propres. Ne pas annoncer une équivalence globale avant ces validations.

## Recette d’acceptation avant une prochaine version

- Merge A+B ; aller à Compress ; revenir : ordre et deux fichiers présents.
- Réordonner A/B/C, retirer B, annuler : retrouver exactement la séquence précédente.
- Ajouter un PDF invalide : voir son erreur, le retirer et traiter les fichiers valides.
- Split 3–1, 0–2, fin hors document, champ vide : erreur locale et traitement bloqué.
- Cliquer une miniature en Range : ne change pas l’onglet actif.
- Split fixe 7 pages par groupes de 3 : contenus vérifiés dans les trois PDF.
- Extraction des pages 1,3–5 : 4 pages regroupées ou 4 PDF suivant l’option.
- Deux plages qui se chevauchent : résultat conforme au contrat annoncé.
- Compress avec deux fichiers : deux résultats, statistiques exactes, aucun fichier oublié.
- Fichier déjà optimisé : message honnête, gain à zéro, original intact.
- Organize et Rotate : vérifier ordre, suppressions et angles dans le PDF produit.
- Annuler import, traitement ou enregistrement : aucune perte de session ni résultat final incomplet.
- Réessayer après erreur d’écriture : résultat disponible et nouveau choix de destination.
- Terminer une tâche, continuer avec le résultat dans un autre outil sans le rechercher sur disque.
- Navigation clavier, molette sur les cartes, fenêtre minimale et nom de fichier long.

## Preuves locales

`reproduce_ux_baseline.py` génère uniquement des PDF synthétiques en répertoire temporaire, ouvre Tk sans fenêtre visible et sonde les actions de l’application. Il ne mesure pas la qualité visuelle et n’automatise pas iLovePDF. La fixture en erreur ne touche aucun document utilisateur.

Repères du code audité : `app.py` — catalogue 96, navigation 206, import 319, previews 335/404, sélection 444, activation 483, traitement 507, résultat 555 ; `pdf_tools.py` — `selection`, `process`, `split_ranges`.
