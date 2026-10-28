# États et correspondance des étapes

Le classement ci-dessous organise la procédure fournie par le porteur du projet ; il ne complète pas ses exigences de sécurité manquantes.

| Étape | Phase proposée | Texture utile | Ce que l’essai peut observer |
|---|---|---|---|
| A-01 | Préparation | S01 ou S02, puis S03 | Configurations candidates fermée/ouverte et lecture des repères |
| A-02 | Consignation : commande | S01 ou S02 | Interrupteur prévu OFF ; sa lecture physique reste à vérifier |
| A-03 | Consignation : séparation | S02 ; négatif S01 | Deux logements vides contre pile présente |
| A-04 | Consignation : stockage | S02 ; négatif S01 | Pile dans réceptacle et absence du support |
| A-05 | Maintenance : accès | S03 ; négatif S02 | Carter dégagé et carré proche du cercle vide |
| A-06 | Maintenance : remplacement | Aucune preuve image | Confirmation humaine normale du travail, pas dérogation caméra |
| A-07 | Remise en service : fermeture | S02 ; négatif S03 | Carter recouvrant la lampe et carré proche du cercle plein |
| A-08 | Remise en service : reconnexion | S01 ; négatif S02 | Pile dans logement fonctionnel, réceptacle vide |
| A-09 | Remise en service : commande et essai | S04 | Lampe lumineuse ; état ON à lire séparément |

S01 : pile dans support / réceptacle vide / carter fermé / bascule prévue OFF / lampe non lumineuse.
S02 : support vide / pile stockée / carter fermé / bascule prévue OFF / lampe non lumineuse.
S03 : support vide / pile stockée / carter ouvert / bascule prévue OFF / lampe non lumineuse.
S04 : pile dans support / réceptacle vide / carter fermé / bascule prévue ON / lampe lumineuse.

Pour A-03 et A-04, la même texture S02 peut représenter les deux résultats observables. Elle ne prouve pas leur ordre d’exécution. Pour A-07 et A-08, l’état de remise en service réutilise les mêmes apparences : aucune nouvelle image artificiellement différente n’est nécessaire.

## Limites constatées par revue visuelle

- Disposition générale conservée : cercles fixes à gauche, plein au-dessus du vide ; carré attaché au bord gauche du carter ; ampoule en haut ; support rouge à gauche, interrupteur à droite ; petit réceptacle en bas.
- Le carter change de position et continue à couvrir la zone lampe dans les états fermés. Il ne s’agit pas d’une reconstruction 3D du guidage.
- Les centres du carré et des cercles présentent de petits écarts résiduels. Ces images NE sont PAS une référence de tolérance « quasi parfaite ». Ne pas abaisser le seuil de la procédure pour leur faire réussir un contrôle.
- Les proportions, la forme de la bascule et le détail de la pile varient légèrement. Ne pas réutiliser automatiquement la calibration physique de la vraie planche sur ces textures.
- Le type électrique et la tension ne sont pas établis par ces illustrations. Les textes de pile générés ne sont pas des données techniques.
- La lampe a un aspect lumineux dans S04 ; cela ne prouve ni l’état électrique réel ni le remplacement de la lampe.
- Pour valider une fidélité géométrique stricte, utiliser des vues réelles rectifiées et calibrées ou un modèle vectoriel/3D mesuré. Ces quatre images servent de fixtures synthétiques complémentaires aux captures originales du premier ZIP.
