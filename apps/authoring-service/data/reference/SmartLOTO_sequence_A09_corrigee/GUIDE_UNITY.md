# Maquette virtuelle SmartLOTO

Ce paquet apporte 29 vues séquentielles SYNTHÉTIQUES générées à partir de la photographie annotée réelle. Les premiers essais qui avaient déplacé les cercles à droite sont exclus. Les textures retenues gardent les cercles à gauche, le support à gauche, l’interrupteur à droite et le petit réceptacle en bas. Elles ne sont ni des photos rectifiées exactes ni un jumeau numérique métrologique : forme du composant, proportions, reflets et alignements peuvent différer du réel. Les utiliser pour une démonstration et pour déceler des problèmes ; pas comme vérité terrain de sécurité.

## Montage dans Unity

1. Copier images/ dans Assets/SmartLOTO/Simulation/Textures/.
2. Créer un matériau Unlit adapté au pipeline du projet et lui affecter une texture. Employer un shader non éclairé empêche l’éclairage de scène de transformer artificiellement l’aspect lumineux prévu de la texture. Une lampe dessinée allumée n’est pas une vraie source d’énergie.
3. GameObject > 3D Object > Quad. Affecter le matériau à son Renderer. Le Quad par défaut est dans le plan local XY, avec une largeur et une hauteur d’une unité. Régler son orientation pour que la face visible soit tournée vers la caméra.
4. Pour un Quad sous des parents d’échelle 1, une largeur W mètres et une hauteur H mètres correspondent à Scale = (W,H,1). Les dimensions de la vraie planche n’étant pas connues, W et H restent des paramètres. 0,20 × 0,30 m n’est qu’un exemple, pas une mesure du prototype. Les textures n’ont pas nécessairement ce ratio : conserver le ratio du fichier ou documenter tout changement de proportions.
5. Préférer Quad à Plane. Un Plane Unity fait par défaut 10×10 unités dans XZ : sa taille se règle différemment et sa rotation aussi.
6. Créer une origine VIRTUELLE de simulation. Si le code impose LOTOOriginAnchor, utiliser un objet équivalent réservé au mode test. Les textures ne contiennent aucun QR ; l’identification et la calibration de test doivent être explicites.
7. Le pivot du Quad est au centre. Placer Quad au localPosition (0,0,0) fait coïncider son CENTRE avec l’origine, pas la position supposée d’un QR. Pour un point UV (u0,v0), origine UV bas-gauche, Quad non retourné, échelle locale (W,H,1) et rotation locale identité : localPosition = (-(u0-0.5)*W, -(v0-0.5)*H, 0). Adapter à la rotation locale réelle et tenir compte des échelles des parents. La position UV réelle du QR doit être renseignée ; elle ne peut pas être déduite des textures générées.
8. Changer de texture pour simuler les états en conservant le même Quad. Contrôler visuellement les petites variations de géométrie entre images ; une calibration unique peut nécessiter un ajustement. Ne pas déplacer arbitrairement les flèches pour cacher une erreur de conversion de coordonnées.

Documentation officielle : https://docs.unity.com/en-us/engine/6000.6/manual/working-with-gameobjects/gameobject-fundamentals/primitive-objects

## Point essentiel : quelle image est analysée ?

Un Quad dans la scène n’apparaît pas automatiquement dans une WebCamTexture. Pour tester la vision sans maquette : utiliser l’import de texture comme entrée du vérificateur, ou une caméra Unity qui rend le Quad dans une RenderTexture. Si on veut tester la perspective, choisir le rendu de caméra. Ne pas inclure les flèches/UI dans la capture envoyée au modèle.

Le placement des flèches depuis des coordonnées connues de la scène teste la géométrie. Il ne prouve pas la localisation visuelle des organes. Un vrai test de localisation doit analyser l’image et comparer le résultat à des cibles de référence indépendantes.

## État de la livraison


Pour les sources et les routes actuelles, consulter [le guide d’intégration Unity](../../../../../docs/UNITY_INTEGRATION_READY.md).
