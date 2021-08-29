# Designing YART

## Multithread Multiprocessing

On peut considérer deux catégories de tâches
- Intensives en E/S ex : capture de caméra, envoi/réception réseau, lecture/écriture de fichiers.
- Intensives en processeur ex : algorithmes de traitement d'image

#### Multithread 

Un thread est un flux d'exécution au sein d'un processus.

Le principal avantage du multithreading est qu'il permet des opérations d'E/S simultanées avec les traitement

Par exemple, du côté de PI, nous avons

- Capture, échange entre l'application et la caméra
-  Envoi de l'image sur le réseau

L'exécution de ces deux opérations dans des threads séparés permet la simultanéité, sinon elles seraient sérialisées. Les threads partagent les données globales de l'application, par exemple l'objet caméra. Python fournit des outils pour la synchronisation et l'échange entre les threads (Event, Queue, ...)

Attention :

L'interpréteur Python a une limitation qui ne permet pas l'exécution simultanée de code Python dans des threads.Le multithreading Python n'est donc adapté qu'aux tâches d'entrées-sorties, il n'apporte aucun gain pour la simultanéité des tâches de calcul. Il faut alors utiliser le multi processing

#### Multiprocessus

Il s'agit de processus distincts qui peuvent alors s'exécuter sur différents cœurs de processeur.
La programmation est plus complexe car les processus ne partagent pas les données en mémoire.
Il faut utiliser des mécanismes de communication inter-processus.

#### Les besoins coté PI

- Réception non bloquante des commandes du client -> Une thread, la thread principale


- Contrôle du moteur pas à pas, envoi du signal PWM sur le GPIO 
  On utilise l'excellent et efficace package pigpio qui permet de contrôler facilement les broches du GPIO du Raspberry.
  Le principal avantage de l'utilisation de pigpio est que le signal PWM pour faire tourner le moteur est effectué dans un processus daemon externe à l'application. Il n'y a donc pas besoin de fournir un thead ou un processus python pour cela.

- Echange avec la caméra, capture de la trame -> Une thread


- Envoi de la trame sur le réseau -> Une thread
  Echange des trames entre la trame de capture et la trame d'envoi par une Queue

En conclusion La charge CPU sur le PI est faible pas besoin de multi-processus
Un multithread simple, trois Thread et une Queue suffisent aux besoins
Multiplier les thread n'apporterait rien de plus puisque la camera et le réseau sont les ressources  non partageables

#### Les besoins coté PC

- Réactivité de l'interface graphique -> Une thread, la thread principale
  Envoi des commandes sur la connexion de commande

- Réception des trames -> Une thread de réception
- Traitement des trames -> Après  réception de la trame un traitement d'images est effectué sur le PC mais a priori sa vitesse est suffisante pour les exécuter dans le thread de réception. Si ce n'était pas le cas, il faudrait envisager du multithread ou du multi-processus ( en Python) .

#### Mesure et vérification de performance :

Il s'agit de déterminer les point bloquants qui pourraient être améliorés pour une meilleure performance. On se pose la question, d'agit-il de la camera, du réseau, de la CPU du Pi,  de la CPU du PC  ? On mesure la performance CPU et réseau avec les outils usuels sur le PC et le PI

On constate dans la configuration actuelle :

- Le réseau Ethernet 100Mb est juste suffisant, à surveiller quand même
- Le PC, dans mon cas un Core I7-4790,  est suffisant . Ne pas lancer de gros traitementd comme encodage ou autre simultanément !
- Il n'y a quasiment jamais de ralentissement dû au réseau ou au PC 
- Le point bloquant c'est la vitesse de capture dans l'échange avec la caméra.



## Programmation réseau MessageSocket.py

Fondamentalement, la communication client-serveur implique un socket TCP. Un socket TCP est un flux de données bidirectionnel entre le client et le serveur. Sur ce flux de données on envoie ou reçoit des octets. C'est donc une communication d'assez bas niveau.

Dans le script MessageSocket.py  nous définissons une classe et diverses méthodes pour un niveau de communication plus élevé

- Envoyer/recevoir un tableau d'octets d'une certaine longueur
- Envoyer/recevoir un tableau NumPy avec ses dimensions (une image RGB par exemple)
- Envoyer/Recevoir n'importe quel objet Python 

Cette dernière méthode facilite considérablement les échanges. Par exemple, on peut facilement envoyer/recevoir une commande avec ses arguments dans une liste ou une liste d'attributs d'objet dans un dictionnaire nom/valeur.

L'objet est sérialisé dans une chaîne de caractères. La chaîne transmise est évaluée à la réception pour reconstruire l'objet. Consulter le code pour la magie de cette évaluation en Python !

Deux connexions réseau sont utilisées, l'une pour les envois de commande/réponse et l'autre pour la transmission des header d'information et des trames.

## Paramètres, attributs

L'application manipule de nombreux paramètres ou attributs pour la caméra et le moteur. Ces paramètres sont traités de manière orientée objet comme des attributs des objets TelecineCamera dérivée de PiCamera  et TelecineMotor.

Pour la caméra, ces paramètres comprennent les attributs de la classe de base PiCamera (shuter_speed, résolution, awb_gains, ...) augmentés de ceux de la classe dérivée TelecineCamera.

Deux méthodes génériques getSettings et setSettings permettent de définir ou de récupérer les attributs d'un objet à partir d'un dictionnaire Nom-Valeur.

Pour la sauvegarde sauvegarde/restauration, le dictionnaire des paramètres peut être écrit et lu dans un fichier npz (camera.npz, motor.npz, ...).

Les dictionnaires de paramètres peuvent également être facilement échangés comme des objets  sur le réseau.

Avec cette conception l'ajout d'un attribut ne nécessite que quelques lignes de code.

## Programmation GPIO TelecineMotor.py

On utilise l'excellent et efficace package pigpio qui permet de contrôler facilement les broches du GPIO du Raspberry.
Le principal avantage de l'utilisation de pigpio est que le signal PWM pour le moteur ainsi que le contrôle des broches comme le trigger est effectué  par un processus daemon externe à l'application, il n'y a donc pas besoin de créer un thead ou un processus pour cela.

Le signal PWM est modulé au démarrage pour un démarrage en douceur et non brusque qui pourrait être bloquant (ramping).

## Contrôle de la caméra  

L'excellente bibliothèque PiCamera, simple et efficace, permet de contrôler la caméra en Python. Notez qu'elle ne provient pas de la fondation Raspberry mais d'un développeur indépendant. Elle n'est plus maintenue par ce développeur ni par la fondation, ce qui est très regrettable. Elle est cependant stable, sans bug majeur et fonctionne bien même avec la nouvelle caméra HQ.

Sa documentation est excellente, notamment sa description du matériel de la Picamera, consultation recommandée !

La capture d'une seule image "Shot" ne pose aucune difficulté.

Une attention particulière est portée à la capture continue la plus efficace possible avec la méthode "capture_sequence". C'est la partie la plus délicate du code avec notamment le traitement du bracketing HDR.

Les images sont capturées en jpeg sur le port vidéo empilées dans une Queue vers la thread d'envoi du réseau.

Avant que l'image on transmet dictionnaire header avec des informations sur l'image. Ces headers sont également utilisés pour transmettre toute information utile entre le PI et le PC.



## Coté PC

#### Interface graphique

L'interface graphique est construite avec PyQT. Le designer PyQT est utilisé pour créer l'interface  TelecineApplication.ui

#### Traitement de l'image sur le PC ImageThread.py

Dans le cas le plus simple, l'image jpeg reçue est affichée et directement sauvegardée dans un fichier.

Si elle doit être traitée, elle est décodée en une image opencv BGR (un tableau numpy).

Le traitement consiste en une fusion de Mertens si bracket

Comme expliqué plus haut en l'état actuel de l'application la puissance du PC est suffisante a priori  pour effectuer le traitement et l'affichage directement dans la thread de réception.  Si ce n'était pas le cas il faudrait distribuer les trames dans des processus de traitement (et non de threads puisque l'on est en Python)