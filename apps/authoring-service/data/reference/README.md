# Référence SL-POC-01

`SL-POC-01-bulb-replacement.draft.json` est le brouillon de référence rédigé
depuis le manuel et la vue fournis. Il n'est pas approuvé ni destiné à être
exécuté tant que les clarifications de premier niveau ne sont pas résolues.

Clarifications ouvertes :

- Fournir deux vues légendées **ouvert** et **fermé** pour confirmer le sens de
  coulissement du carter. La correspondance carré + cercle vide = ouvert et
  carré + cercle noir plein = fermé est conservée comme décrite dans le manuel,
  en attente de confirmation visuelle.
- Confirmer si la cible est une ampoule incandescente ou une LED : le texte et
  la légende de la photo divergent.

La photo reçue montre une seule configuration et ne suffit pas à établir les
deux positions du carter. Le endpoint de génération actuel n'analyse pas les
pixels de la photo; son mode `source_type=image` doit être considéré comme
texte seul tant qu'une intégration vision réelle n'est pas ajoutée.

Chaque contrôle de présence/état reste distinct. Une occultation du support de
pile produit un état indéterminé; la validation du remplacement de l'ampoule
est une confirmation opérateur; le contrôle final ne constitue pas une preuve
que le remplacement a eu lieu.
