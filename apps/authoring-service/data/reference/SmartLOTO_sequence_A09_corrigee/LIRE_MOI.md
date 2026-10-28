Archive compatible : 29 images JPEG haute qualité, dimensions conservées. Les extensions du fichier timeline sont mises à jour.

Version révisée : lire aussi REVISION.md.

# SmartLOTO — 29 vues pour 9 étapes

Les fichiers 01 à 29 sont à lire strictement dans l’ordre. Chaque étape a un état AVANT, un geste et un état APRÈS ; A-06 a cinq vues pour détailler le remplacement. Les vues AVANT/APRÈS peuvent être identiques à la fin/début de deux étapes successives : c’est volontaire, pour conserver la continuité du scénario.

Ces images sont des illustrations SYNTHÉTIQUES de simulation, inspirées de la photographie réelle. Elles ne prouvent pas une intervention réelle et ne garantissent pas une géométrie rigoureusement identique à la maquette. Les états intermédiaires de coulissement représentent un mouvement, pas une position intermédiaire stable autorisée.

## Parcours

| Étape | Phase | Images | Résultat narratif après l’étape |
|---|---|---|---|
| A-01 | Préparation | 01–03 | Observation de l’état initial : carter fermé, pile connectée, lampe allumée |
| A-02 | Consignation : commande | 04–06 | Commande OFF, lampe non lumineuse ; pile encore connectée |
| A-03 | Consignation : séparation | 07–09 | Pile retirée et tenue en main, support et réceptacle vides |
| A-04 | Consignation : stockage | 10–12 | Pile déposée dans le réceptacle, support vide |
| A-05 | Maintenance : accès | 13–15 | Carter ouvert, pile stockée, lampe non lumineuse |
| A-06 | Maintenance : remplacement | 16–20 | Ancienne lampe retirée, remplacement illustré, lampe en place ; confirmation humaine |
| A-07 | Remise en service : fermeture | 21–23 | Carter fermé, pile toujours stockée |
| A-08 | Remise en service : reconnexion | 24–26 | Pile réinsérée, réceptacle vide, commande OFF |
| A-09 | Remise en service : commande/essai | 27–29 | Commande prévue ON et lampe lumineuse |

Ce classement organise le prototype didactique, il n’atteste pas une procédure industrielle complète de consignation/verrouillage/étiquetage. Aucun cadenas physique n’est créé à partir du pictogramme.

## Tester les vérifications

- Ne pas valider la fin d’un geste à partir de sa seule image de transition : pile partiellement insérée, pile au-dessus du réceptacle, main masquant un repère, carter en mouvement.
- Évaluer les critères observables de l’étape courante, pas l’ordre des noms de fichiers. Le modèle ne reçoit ni le nom de fichier ni l’état attendu.
- Pour A-06, la confirmation humaine est la validation normale de maintenance, pas une dérogation. L’image finale seule est visuellement identique à l’état ouvert avant remplacement et ne prouve pas que le composant est neuf.
- ON/OFF doit être lu sur la bascule ; une lampe éteinte n’est pas une preuve d’isolement. Les bascules générées et les alignements restent à apprécier visuellement ; ne pas abaisser les critères pour faire réussir ces fixtures.
- Une absence de cible ou une occlusion doit donner un résultat indéterminé si le critère ne peut pas être observé. Une erreur serveur n’est pas un critère contredit.
- Ne pas avancer automatiquement une intervention réelle avec ces images. Utiliser une session TEST séparée.

## Affichage Unity

Importer les images comme textures ; réutiliser le même Quad et changer son matériau/sa texture dans l’ordre. Chaque image est un instant de démonstration, pas une vidéo ni une animation continue : les mains peuvent changer légèrement d’aspect entre vues. Le Quad reste à une pose fixe pour commencer, puis tester sa rotation et la caméra.

Une webcam ne voit pas automatiquement le Quad Unity : envoyer au vrai vérificateur soit la texture importée soit une RenderTexture d’une caméra Unity qui voit le Quad. Pour tester perspective et placement des flèches, employer la capture de cette caméra. Exclure les flèches/UI du rendu envoyé au modèle.

L’origine de simulation et l’échelle réelle doivent être configurées. Le pivot du Quad est au centre ; il ne correspond pas automatiquement au QR. Les dimensions et l’emplacement réel du QR ne sont pas fournis. Les textures ne contiennent aucun QR.

Le paquet contient aussi GUIDE_UNITY.md, complétés pour le parcours séquentiel. Aucun code applicatif ni Unity n’a été exécuté ici. Les essais effectués ici portent sur la préparation et l’intégrité du paquet ; les images ont été revues visuellement.
