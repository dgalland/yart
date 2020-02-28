# Yet Another Raspberry Pi Telecine

En premier lieu je dois remercier Joe Herman pour son projet https://github.com/jphfilm/rpi-film-capture. Mon projet n'est pas un fork car toute la partie logicielle a été réécrite. Cependant toute la partie matérielle reprend les idées de Joe.

## Hardware

### Raspberry

Raspberry PI 3 Modèle B+

Question du Raspberry P4: Dans cette application, les opérations d'entrée sortie, capture de l'image et envoi sur le réseau sont le facteur bloquant pour la performance et exécutées dans des threads séparées. L'application ne demande pas beaucoup de puissance CPU. Le Raspberry PI4 plus puissant n'apportera pas un gain significatif. Noter quand même que le PI4 a une meilleure performance réseau car l' interface réseau est indépendante  du bus USB, il peut y avoir un gain de ce coté.

### Caméra et optique

Il faut faire les choix suivants:

- Picamera V1 ou V2
- Avec l'objectif d'origine ou un objectif adapté
- Montage direct ou reverse

Noter que le filtre IR est indispensable.

La camera V1 utilise un capteur Omnivision 5647 5MP de taille 3.76 × 2.74 mm, de résolution maximale 2592x1944 et de distance focale3,6 mm  et la camera V2 un capteur SONY IMX219 de taille 3,68x2,76mm de résolution maximale 3280*2644 et de distance focale 3,04mm.

Cf. <https://www.raspberrypi.org/documentation/hardware/camera/>

La taille d'une image 8mm est de  4,5mmx3,3mm et celle d'une image Super 8 5,79x4,01mm. En première approximation le grossissement n'est pas très différent de 1.  Dans ce cas la distance du centre de l'objectif à l'image et du centre de l'objectif au capteur sont à peu près deux fois la distance focale. La distance de totale l'image au capteur à peu près quatre fois la distance focale. On est dans le domaine de la photographie macro.

Deux solutions sont alors possibles:

- Conserver l'objectif d'origine de la picamera l'ajuster au maximum et lui ajouter une lentille maco
- Une camera avec une monture M12 ou CS et un objectif de plus grande focale

Je n'ai pas étudié ni fait le calcul optique pour la première solution.

Pour la seconde solution est une camera Raspberry V2 8MP Arducam avec monture CS et un objectif de 35mm le calcul optique montre:

- Image film 8mm 4,5x3,3 mm Capteur IMX219 3,68x2,76mm Grossissement 0,81 

- 30mm de bagues d'extension
- Distance bague de l'objectif/Capteur 46mm Distance Face avant de l'objectif/Image 61mm
- Distance totale Image/capteur 141 mm

Voir l'image du montage ci-dessous

### Camera V1 ou V2 ? Calibration

Malheureusement utiliser un objectif non stock avec les caméras V1 et V2 entraine un vignettage et une dérive de couleur sur les bords de l'image que l'on doit corriger en calibrant la camera et en construisant une "lens shading table" qui contient des gains pour les différentes couleurs de façon à obtenir une image uniforme.

Cf. <https://www.raspberrypi.org/forums/viewtopic.php?t=190586>

Ci dessous une image uniformément blanche capturée avec la V2 sans calibration:

![WhiteFlat](images/WhiteFlat.jpg)

Puis avec calibration:

![WhiteCalibrated](images/WhiteCalibrated.jpg)



On peut penser que la calibration est réussie mais ce n'est pas le cas ! 
Ci dessous les images prises avec des filtre RGB et des histogrammes de la répartition des couleurs suivant les axes de l'image.
(Attention il n'est pas certain que mes filtres soient exactement les couleurs primaires monochromatiques)



![Red](images/Red.jpg)

![Green](images/Green.jpg)

![Blue](images/Blue.jpg)

Le résultat est très mauvais, surtout pour le rouge, combiné avec le vert et le bleu cela peut donner pour certaines images un rond central plus jaune.  Ci-dessous un exemple réel calibré/non calibré:

![v2](images/v2.jpg)


La zone jaune est bien visible au centre de l'image calibrée

En conclusion, il semble difficile d'obtenir une bonne calibration pour la V2 avec un objectif non stock.

Reprenons maintenant cette étude avec la V1.

Image Blanche non calibrée

![WhiteNoneV1](images/WhiteNoneV1.jpg)

Image blanche calibrée

![WhiteCalibratedV1](images/WhiteCalibratedV1.jpg)

Filtre rouge:

![RedV1](images/RedV1.jpg)

Filtre vert

![GreenV1](images/GreenV1.jpg)

Filtre bleu

![BlueV1](images/BlueV1.jpg)

Et pour une image réelle
Haut: Non calibré/calibré
Bas:Merge/Merge égalisée voir ci-dessous pour le merge

![v1](images/v1.jpg)

En conclusion la camera V1 semble vraiment un meilleur choix. Cependant l'image corrigée n'est pas totalement uniforme, surtout pour le rouge

### Capture au centre du capteur sans calibration

Au centre du capteur l'image est presque correcte même sans calibration. On peut donc sélectionner une ROI (Region of interest) au centre.  Par exemple avec la V1 en résolution 2592x1944 on peut sélectionner une ROI HD 4/3 de 1440x1080. Ci-dessous les histogrammes de répartition au centre sans calibration, 

![V1_center](images/V1_center.png)

Il y a seulement une plus de luminosité sur les cotés.

Par contre l'image objet est plus petite, il faut moins de bagues d'extension et éloigner la camera de l'image.

### Capture au centre et calibration locale

Une autre possibilité est d'exécuter la correction de calibration non pas coté du PI avec la table lens_shading mais coté du PC . Ci-dessous les histogrammes de répartition au centre avec calibration locale

![V1_center_local_calibrated](images/V1_center_local_calibrated.png)

 C'est la solution qui combinée avec la capture au centre m'a donné le meilleur résultat.

### Lampe, Diffuseur

J'ai de bon résultats avec une LED TrueColor Phillips faisceau étroit 4000K (avec réflecteur GU5-3 MR16) )

Le choix de la matière et de l'emplacement du diffuseur est très important

- Sans diffuseur les rayons lumineux directs vont accentuer les défauts et les rayures du film.
- Un mauvais diffuseur va entraîner une perte de netteté.

Après beaucoup d'essais j'ai obtenu le meilleur résultat avec un diffuseur assez épais (1,5mm) de plastique translucide placé au plus près du film (5mm) qui donne un éclairage complètement indirect similaire à celui des scanner professionnels.  La LED est à environ 10cm du film sans aucun diffuseur.

 Il faut ajuster la distance de la lampe et le diaphragme de l'objectif pour avoir une durée d'exposition convenable. Si la caméra fonctionne à 30fps l'exposition maximum est de 33333 micro seconds. Si le bracketing (cf infra) est utilisé il faut que l'exposition auto sur une image normale soit d'environ 2000 à 3000 micro-secondes.

  ### Projecteur, Trigger, Moteur

Mon projecteur est un Elmo GP, il faut enlever toutes les parties électriques et conserver uniquement le mécanisme d'avancement du film. Il faut enlever la pale avec les trois fenêtres et la remplacer par un disque avec un capteur "trigger" qui se déclenche quand l'image est bien positionnée dans la fenêtre de projection. J'utilise un capteur optique qui se déclenche au passage d'un petit trou dans le disque.

Si possible agrandir au maximum ou supprimer la fenêtre de projection pour capturer la totalité de l'image.

Le moteur pas à pas est un moteur NEMA 17 alimenté en 24v. Comme contrôleur j'ai choisi un TB6600 qui présente certains avantages, les hauts voltages sont bien séparés des broches du Pi (moins dangereux pour le Pi !), les broches sont protégées par des coupleurs optiques et le micro-stepping et l'intensité sont contrôlables par des switchs 

Le moteur entraine l'axe du projecteur par des poulies GT, avec un ratio de 1:1

Maintenant quelques images:

Le projecteur, la caméra et la lampe. Une petite table micrométrique permet une mise au point précise.



![1](images/1.jpg)

Le moteur et le disque avec le capteur optique. Les équerres pour rigidifier et éviter les vibrations.

![2](images/2.jpg)

De gauche à droite: Alimentation 24v, Contrôleur TB6600, breadboard et Raspberry et son alimentation 5V

![3](images/3.jpg)

## Software

L'application Python reprend l'idée de Joe, une application client-serveur communiquant par le réseau. L'application sur le Raspberry contrôle le moteur et la caméra, les images capturées sont envoyées à l'application sur un PC windows pour traitement et sauvegarde. Le GUI de l'application windows envoie des commandes à l'application Pi et reçoit des réponses. Maintenant quelques détails d'implémentation.

### Programmation réseau

Le mécanisme des sockets est utilisé pour la communication réseau. Une classe `MessageSocket` permet sur un socket des envois ou réceptions orientés objet

- Envoi et réception d'un buffer
- Envoi et réception de string
- Envoi et réception d'un objet python quelconque (dictionnary, tuple, ...)

Ainsi on peut aisément envoyer ou recevoir sur ce socket toute sorte d'objets Python, commande et ses paramètres, réponse, dictionnaire d'attributs, header de frame avec des informations, image JPEG ou tableau numpy

Deux sockets sont utilisés, un socket bidirectionnel pour envoyer des commandes et recevoir des réponses et un socket unidirectionnel pour recevoir les frames et des headers d'information.

### Attributs d'objet

L'objet camera et l'objet motor ont des attributs de propriétés. Des méthodes génériques get et set permettent d'y accéder. Ces attributs sont sauvegardés sous forme de dictionnaires python avec Numpy (fichiers npz). Les objets dictionnaires d'attributs peuvent aussi être transmis sur le réseau. Ces méthodes génériques permettent facilement de gérer un grand nombre d'attributs sans alourdir la programmation.

### Moteur

On utilise la librairie pigpio qui permet de générer les pulses PWM par hardware en dehors de l'application Python. C'est plus précis et ne ralentit pas l'application. La librairie pigpio permet aussi dé démarrer le moteur en contrôlant l'accélération pour éviter de le bloquer (ramping).  Le moteur peut fonctionner en continu à une certaine vitesse ou bien en discontinu frame by frame avec arrêt sur le trigger.

Câblage du moteur

Deux broches sont absolument nécessaires PUL/STEP et DIR
Unr broche supplémentaire ENA ou RESET peut être utilisée pour mettre le moteur ON/OFF. En fait il n'y a pas d'inconvénient à le laisser sous tension si ce n'est que son couple empêche d'avancer le projecteur manuellement.

Contrôleur TB6600

ENA- PUL- DIR- to GND
ENA+ DIR+ PUL+ To Pi GPIO 
Si ENA+ HIGH le moteur est Off Line 

Contrôleur DRV8825

STEP DIR and SLEEP to Pi GPIO
RESET non utilisé à connecter sur Pi VDD 3.3V
Si SLEEP est HIGH le moteur est On Line

Un moteur pas à pas fonctionne en général à 200 pulses par tour. Utiliser le micro-stepping par exemple à 800 pulses par tour peut diminuer les vibrations

### Camera	

Bien entendu on utilise la librairie Python picamera. Cependant comme indiqué plus haut la camera avec un objectif non d'origine produit une image très mauvaise. Il est absolument nécessaire de calibrer l'objectif en construisant une table de correction `lens_shading_table`. Cette modification n'est pas encore comprise dans la version actuelle de la librairie, il faut donc  installer et utiliser une version spéciale de la librairie., On pourra se référer au projet:

https://github.com/rwb27/openflexure_microscope_software

La capture s'effectue en JPEG sur le port video 

Comme expliqué dans la documentation picamera on utilise la méthode la plus rapide `capture_sequence` avec un générateur. 

https://picamera.readthedocs.io/en/release-1.13/

En théorie dans le générateur deux méthodes de capture sont possibles

#### Capture "On frame"

Le moteur est asservi à la capture

```
Tant que captureEvent
	Avancer le moteur jusqu'au trigger
	Capturer la frame
	Envoyer la frame sur le réseau
```

#### Capture "On trigger"

La capture est asservie au moteur

```
Démarrer le moteur à une certaine vitesse
Tant que captureEvent
	Attendre le trigger
	Capturer la frame
	Envoyer la frame sur le réseau
```

Dans la première méthode le moteur avance de façon discontinue, frame par frame, dans la seconde il tourne à vitesse constate, le trigger déclenche la capture. 	

### Paramètres de la caméra, Bracketing, Merge, HDR

La camera est limitée dans sa dynamique, si on augmente l'exposition pour éclaircir les sombres, il n'y a plus de détails dans les clairs et inversement. Il est pratiquement impossible d'obtenir une image qui reflète correctement toutes les luminosités de la scène.

C'est pourquoi il est absolument nécessaire de reprendre l'idée de Joe et de capturer chaque image avec différentes expositions (bracketing), une sous-exposée pour obtenir les clairs, une surexposée pour obtenir les sombres et une normale, avant de les fusionner. Ce traitement sera fait coté PC avec la librairie openCV.

Plusieurs algorithmes de fusion Merge/HDR sont disponibles. Le plus simple utilisé par Joe est le Merge Mertens, les pixels sont fusionnés en ignorant les pixels trop blancs ou trop noirs. 

Les algorithmes de vrai HDR tentent de rendre compte de ce que verrait un œil humain en corrigeant l'imperfection de la caméra. 

On peut se référer à :
[https://www.learnopencv.com/high-dynamic-range-hdr-imaging-using-opencv-cpp…](https://www.learnopencv.com/high-dynamic-range-hdr-imaging-using-opencv-cpp-python/)
et
<https://www.learnopencv.com/exposure-fusion-using-opencv-cpp-python/>

Comme exemple, ci-dessous la même image avec 25 expositions également réparties en luminosité. On constate que <u>aucune image n'est vraiment satisfaisante</u>. Quand on commence à voir le fond sombre les blancs sont surexposés. la dernière image bien meilleure est le résultat d'un merge HDR (MergeDebevec et TonemapReinhard)

![result (2460 x 1540)](images/result.jpg)

Autre exemple, l'image sous-exposée,  l'image avec l'exposition automatique, l'image sur-exposée puis l'image merge Mertens et l'image HDR. L'image Mertens est un peu artificielle car elle ne rend pas compte de la luminosité réelle de la scène, les sombres sont exagérément accentués. On constate également que le merge Debevec réduit le grain par contre elle manque de contraste ce qui pourra être amélioré au post-traitement.

![merge](images/merge.jpg)

​                                                              Bracket de 3 Merge Mertens et Merge Debevec

###### Mise en œuvre du merge

D'un point de vue programmation la mise en œuvre du bracketing est très délicate, en effet il faut bien avoir l'idée que la caméra n'est pas un appareil photo mais une caméra qui fournit un flux continu d'images.  Donc après avoir changé l'exposition il faut attendre quelques frames (minimum 4 d'après mon expérience) avant d'obtenir la bonne exposition. De même après  être repassé en automatique il faut attendre quelques trames (minimum 8 d'après mon expérience) avant d'avoir la bonne exposition. La capture devient:

```
Tant que captureEvent
	Avancer le moteur jusqu'au trigger
	Attendre 8 frames
	Répéter 3 fois
		Changer l'exposition
		Capturer la frame
		Envoyer la frame sur le réseau
		Attendre 4 frames
	Repasser en exposition automatique
```

Tout ceci diminue considérablement la vitesse de capture, avec la résolution 1640x1232 elle ne dépasse plus 1s par trame et en résolution 3280x2664 3s par trame.

Pour la mise en œuvre du merge dans l'application voir  ci-dessous

### GUI on the PC

Comme dans le projet de Joe le GUI sur le PC Windows est réalisé avec PyQt5

### Multithreading Multiprocessing

Ces deux techniques ont de buts différents. Un traitement multithread permet d'effectuer simultanément des opérations d'entrée-sortie sans bloquer l'application. Un traitement multiprocessus permet de tirer partie des différent cores du processeur. Noter que normalement des thread pourraient exécuter du code simultanément mais ce n'est pas possible en Python, donc en Python les threads sont pour des applications intensives en IO et les processus pour des applications intensives en CPU.

Sur le Pi aucun traitement intensif en CPU n'est effectué, le contrôle du moteur et du trigger sont effectués en dehors de l'application par pigpio donc le multiprocessus ne s'impose pas. Par contre pour pouvoir effectuer concurremment la capture et l'envoi sur le réseau le multithread est indispensable. Donc sur le Pi on a les threads suivants

- La thread principale avec la boucle de réception des commandes
- La thread de capture
- La thread d'envoi des trames sur le réseau

La communication entre les deux threads est assurée par une Queue d'images et de headers

Sur le PC windows le GUI est réalisé avec Qt on a les threads suivants		

- La thread principale avec la boucle d'évènements de Qt, envoi des commandes et réception des réponses.
- Une thread pour recevoir et traiter les images

Ici aussi on pourrait avoir une thread de réception et une thread de traitement mais ce n'est pas vraiment nécessaire. Le multiprocessus n'est pas non plus nécessaire car le PC est suffisamment puissant.

Il est intéressant de noter que le réseau n'est pas un facteur limitant, avec la résolution 1640x1232 et une capture à 1fps, le débit réseau est d'environ 20mb/s. L'interface réseau du Raspberry est indiquée comme 1Gb/s mais en réalité elle utilise le bus USB donc plus lente.

## Installation and setup

L'application nécessite python 3 sur le PC et sur le Pi.

Le 28/02/2020 j'ai refait une installation complete 

Sur le PC Windows

- Python 3.8.2
- pip install mathplotlib
- pip install numpy
- pip install opencv-python
- pip install opencv-contrib-python
- pip install PyQt5

Si on veut utiliser de designer PyQT pour modifier l'interface graphique

- pip install pyqt5-tools

Si on utilise l'IDE Thonny, il est préférable de l'installer dans Python lui-même plutôt que d'installer la version qui comprend une autre installation de Python:

- pip install thonnyapp

Sur le Pi raspian:

Python est en version 3.5.3

- pip3 install numpy
- pip3 install pigpio

Pour la librairie picamera si on n'utilise pas la calibration coté du PI :

- pip3 install picamera 

Si on utilise la calibration il faut installer la version du projet openflexure de Richard Bowman

```
wget https://github.com/rwb27/picamera/archive/lens-shading.zip
pip3 install lens-shading.zip
rm lens-shading.zip
```

Pour plus de commodité l'archive est également dans le répertoire Raspberry de mon projet

## Usage

Ci-dessous l'interface de l'application sur le PC

![gui](images/gui.jpg)

### Exécuter l'application

- Sur le PC dans le répertoire GUIControl exécuter: python TelecineApplication.py

- Sur le Raspberry exécuter le démon  pigpiod : sudo pigpiod

- Sur le Raspberry dans le répertoire Raspberry exécuter: python3 Controller.py

- Sur le PC saisir l'adresse IP du Raspberry et cliquer "Connect"


### Ouvrir la camera

Le plus simple est de choisir un sensor_mode prédéfini , le mode 2 en résolution maximale

https://picamera.readthedocs.io/en/release-1.13/fov.html#sensor-modes

La résolution sera alors la résolution par défaut de ce mode. On peut aussi spécifier la résolution désirée.

Modes d'ouverture de la camera:

- None: Sans table de lens shading
- Flat: Avec une table de lens-shading uniforme
- Calibrated: Avec une table de lens shading calculée comme ci-dessous

### ROI et capture au centre

On peut sélectionner une région de capture. Par exemple dans mon cas la caméra V1 est ouverte en résolution maximale 2592x1944 et je sélectionne une région 1440x1080 au centre du capteur.

### Analyse de l'objectif et calibration

Pour analyser et calibrer l'objectif il faut capturer une image <u>uniformément blanche</u> (pas de cadre noir par exemple). Si un diffuseur est utilisé on peut le faire simplement sans le film dans la fenêtre de projection, ajouter un diffuseur ou fermer le diaphragme si la luminosité est trop forte.

Le bouton "Analyse" calcule un histogramme de répartition des couleurs le long des axes de l'image. Si la camera est ouverte sans calibration il permet de mettre en évidence le phénomène. Après calibration l'histogramme doit être presque plat.

Deux modes de calibration sont possibles:

- Calibration sur le PI , programme repris du projet openflexure cité ci-dessus. Il crée un fichier calibrate.npz qui contient la lens_shading_table et qui sera utilisé à la prochaine ouverture de la caméra.
- Calibration locale sur le PC. Calcul d'une matrice de correction qui sera appliquée à l'image reçue

Les analyses ci-dessus montrent que même pour la V1 la calibration coté du PI n'est pas parfaite. Pour moi le meilleur résultat est obtenu avec une capture au centre et une calibration locale.

Attention la calibration doit être effectuée à nouveau chaque fois que l'éclairage est changé ou déplacé.

### Contrôle du moteur

En premier lieu paramétrer le nombre de steps par révolution, le ratio des poulies Moteur/Projecteur  et les numéros de pins. Pour chaque pin choisir le niveau du signal HIGH ou LOW.

La pin ON contrôle le moteur ON/OFF

Par exemple pour le TB600
ON correspond à la pin ENA+ level LOW
PULSE correspond à la pin PUL+ level HIGH
DIR correspond à la pin DIR+ choisir level pour avoir le bon sens de rotation

Pour le DRV8825
ON correspond à la pin SLEEP level HIGH
PULSE correspond à la pin STEP level HIGH
DIR correspond à la pin DIR choisir level pour avoir le bon sens de rotation

 Le niveau HIGH ou LOW de la pin TRIGGER dépend du senseur utilisé
Par exemple pour mon capteur optique le niveau est LOW quand le trou est détecté.

Le moteur peut tourner en avant ou en arrière à une certaine vitesse ou par image

### Paramètres de la caméra

Color:  L'algorithme AWB de la Picamera ne donne pas toujours de bon résultats et peut causer des fluctuation durant la capture. Il est conseillé de laisser "off" avec des gains fixés à une valeur raisonnable pour donnera une image avec des couleurs au plus près de la réalité du film.

Shutter: Il est conseillé de laisser 0  "automatic exposure" . On peut jouer sur compensation (comme une ouveture du diaphragme)

Gains: Laisser sur auto, les gains analog et digital doivent rester à 1

### Contrôle de la caméra

- Shot: Capture une image (sans bracket)


- Preview: Capture sans avance du moteur, utile pour tester la mise au point, les paramètres de la caméra et le bracket
- Capture: Capture en avançant le moteur. 

"On Frame" Le moteur avance jusqu'au trigger, stoppe puis capture
"On trigger" Le moteur avance de façon continue à une certaine vitesse, la capture est déclenchée par le trigger

La méthode "On frame" est plus fiable surtout si le bracket est utilisé.

### Bracketing et fusion

L'exposition "auto" fait déjà un bon travail en ajustant automatiquement le temps de pose pour chaque image, cependant la dynamique de la caméra est limitée. Le bracketing ou HDR permet d'améliorer considérablement la dynamique de l'image :

- Pour les zones très claires éviter les "Blancs brulés" et retrouver les détails
- Eclaircir les zones sombres pour retrouver les détails 

Il faut ajuster divers paramètres:

- "Dark" coefficient à appliquer à l'exposition de l'image normale (auto exposition calculée par la caméra) pour obtenir l'image sous-exposée. 
- "Light" coefficient à appliquer à l'exposition de l'image normale (auto exposition calculée par la caméra) pour obtenir l'image sur-exposée. 
- "Wait between" Nombre de trames à ignorer après le changement d'exposition (minimum 4)
- "Wait before" Nombre de trames à ignorer après le passage en auto pour l'image suivante (minimum 8). 

Les coefficients "Wait between" et "Wait before" sont nécessaires pour donner à la caméra le temps de s'ajuster après un changement d'exposition pour une même image ou le passage en auto pour l'image suivante.

Pour ajuster ces coefficients il faut faire des essais sur une image dans votre film. 

Sans "Merge" mais avec "Save" choisir "Preview" framerate 10fps

- Vous devez bien voir dans la fenêtre de visualisation et dans le répertoire de sauvegarde les trois images dans l'ordre (sous-exposée, sur-exposée, normale) sinon il faut augmenter "Wait between" pour laisser le temps à la caméra d'ajuster l'exposition.
- De plus l'exposition auto de la trame normale doit être stable, sinon il faut augmenter "Wait before" pour laisser le temps à la caméra de revenir en exposition automatique.

Avec merge "Mertens" ou Debevec vous pouvez ensuite constater l'effet de la fusion

Le réglage des coefficients "dark" et "light" est assez délicat. 

- Le coefficient "dark" détermine l'image sombre sous exposée qui va assombrir et retrouver les détails dans les blancs et éviter les blancs "brulés". L'image sous exposée doit être presque noire sauf sur les blancs très fort sinon elle assombrira toute l'image. Si elle est complètement noire elle n'aura aucun effet.
- Le coefficient "light" détermine l'image claire surexposée qui va éclaircir et retrouver les détails dans les zones sombres. Si elle est complètement blanche elle n'aura aucun effet.

Le merge "Debevec " est le plus difficile à ajuster, il donne une image qui manque de contraste qui devra être égalisée au post-traitement. Il a aussi pour effet de réduire la netteté. Le merge "Mertens" est plus facile à ajuster et semble préférable

Avec la V1 le merge Mertens Dark=0.1 et Light=2 m'a donné de meilleurs résultats.

Ensuite vous pouvez faire les mêmes essais en "Capture"

Au final avec bracket et un framerate  camera de 30fps vous devez obtenir un débit d'environ 1 seconde par image en résolution 1640x1232  et 3 secondes par image en résolution maximale 3280*2464 

### Traitement des images

Il s'effectue sur le PC

- "Histo" affiche l'histogramme de l'image
- "Sharpness" Evalue et affiche la netteté de l'image pour une bonne mise au point (utiliser "Shot" ou "Play" avec 5fps) . La meilleur mise au point correspond à la valeur maximum de sharpness. 
- Reduce permet de réduire la taille de l'image affichée
- "Merge"  Détermine l'algorithme de fusion choisi "None"  "Mertens" ou "Debevec"
- "Save" Sauvegarde les images dans le répertoire choisi. On peut choisir un numéro de bande et un numéro de clip. Pour chaque "Capture" les images sont numérotées à partir de 0
- Calibrate local correction de l'image avec la matrice de correction local

### Post Traitement

Après la capture pour créer un fichier MJPEG (sans réencodage)

 	ffmpeg -framerate 16 -start_number 00000  -i image_%05d.jpg -codec copy 17_01.avi

Pour regrouper des clips:

​	ffmpeg -i "concat:17_01.avi|17_02.avi" -c copy 17.avi

Pour la restauration, stabilisation, cleaning, degrain, sharpness, final white balance and levels, interpolating or blending, ... voir les scripts avisynth de videofred

​	https://forum.doom9.org/showthread.php?t=144271

C'est un peu ancien mais cela reste une référence.

Encodage direct en sortie du script en AVC ou HEVC avec MeGui

Ou bien sûr tout autre éditeur Video

### Nettoyage des films Wetgate

Pour le nettoyage des films le mieux sont les lingettes microfibre pour les lunettes.

Les avis sont partagés sur le solvant à utiliser, produit spécifique onéreux, essence type C, ... Pour ma part j'utilise Shellsol D40, désaromatisé donc un peu moins toxique.

Dans un premier temps on peut nettoyer le film dans un passage à la visionneuse.

Pour les craquelures et  rayures, j'ai mis en œuvre un wetgate simplifié (une idée initiale de videofred et des suggestions de Alain Raynaud)

![20190829_200131](images/20190829_200131.jpg) 

La lingette microfibre est imbibée d'un mélange 50/50 Shellsol D40 et huile de paraffine, me pas mettre trop de produit, quelques gouttes suffisent.

Lé résultat est spectaculaire:

![wetgate](images/wetgate.jpg)



### Expériences utilisateurs

Le montage de Alain Raynaud

- Camera V1 en mode 4
- Objectif 35mm 
- Capture sans bracket en mode trigger
- AWB off après réglage des gains rouge et bleu

​	![P1050447](images/P1050447.JPG)	
​		![P1050449](images/P1050449.JPG)

![P1050448](images/P1050448.JPG)