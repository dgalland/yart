# PostProcessing

Après la capture pour créer un fichier MJPEG (sans réencodage)

 	ffmpeg -framerate 16 -start_number 00000  -i image_%05d.jpg -codec copy 17_01.avi

Ce fichier doit ensuite être traité pour restauration puis montage final avec un éditeur NLE

## Les étapes de la restauration

Les étapes classiques d'une restauration sont :

- Resize et crop éventuel

- Deshake Stabilisation
- Cleaning Nettoyage 
- Degrain Supression du grain
- Sharpening
- Colors and levels : Couleurs et niveaux
- Ajustement du fps

Dans mon cas la capture me donne directement la résolution voulue 1440x1080 donc pas de resize ni crop.

L'ajustement final du framerate avec duplication de frame ou interpolation était nécessaire pour obtenir par exemple un framerate de 24 pour un DVD ou autre. Il n'est plus vraiment nécessaire avec les players modernes on peut très bien rester en 16fps

De nombreux produits commerciaux  traitent tout ou partie de ces étapes préalablement ou intégrés à l'éditeur NLE, nous décrirons ici l'utilisation d'Avisynth. Avisynth reste une référence pour ces traitements mais son évolution est un peu chaotique et son utilisation peut s'avérer complexe. Les problèmes sont nombreux:

- Différentes versions Avisynt 2.6, Avisynth+,  32 bits ou 64bits, Multithread ou non
- Plugins de traitement qui peuvent être anciens, disponibles en 32 bits uniquement, et qui peuvent nécessiter des versions anciennes des DLL Microsoft Visual C/C++.

Mon expérience m'incite à conseiller de rester à une version 32 bits et de ne pas utiliser MT même si le traitement est plus long.

L'exécution des scripts avisynth s'effectue au sein d'un autre produit Virtualdub. A conseiller le fork plus récent VirtualDub2.

Virtualdub comporte aussi un système de plugins moins complet cependant que ceux d'avisynth.

## Installation d'avisynth et Virtualdub2

A conseiller Avisynth Universal installer qui permet d'installer toutes les versions d'Avisythn avec une procédure batch qui permet de choisir la version à utiliser

https://www.videohelp.com/software/Universal-Avisynth-Installer

Mon expérience m'incite à conseiller de rester à une version 32 bits Avisynth + et de ne pas utiliser MT dans le script même si le traitement est plus long.

Ensuite récupérer tous les plugins nécessaires et les installer dans un répertoire

## La restauration

Pour les scripts de restauration la référence reste les scripts de videofred "The power of Avisynth : restoring old 8mm films.

https://forum.doom9.org/showthread.php?t=144271

Pour ceux qui voudraient utiliser Avisynth sans se compliquer la vie avec le choix des scripts on peut conseiller Film9

https://contact41766.wixsite.com/film9

Un script complet avec toutes les étapes est très long à exécuter et l'on peut vouloir essayer de nombreux ajustements. Pour ma part j'effectue la première étape de deshaking une fois pour toutes avec l'excellent plugins deshake de virtualdub et sortie dans un fichier avec un codec looseless dans mon cas MagicYUV mais on pourrait utiliser Lagarith. On évite ainsi de réexécuter plusieurs fois cette étape assez longue. On pourrait aussi séparer l'étape "cleaning, denoising, sharpening" et celle "color and levels". Evidemment dans ce cas il vous faut beaucoup de capacité disque pour les fichier intermédiaires.

Après le deshake, mon script de restauration proprement dit  est une version allégée et modifiée du script de videofred

```
Import("E:/Avisynth/plugins_fred//03_RemoveDirtMC.avs")
LoadPlugin("E:/Avisynth/plugins_fred/MVTools2.dll")
Loadplugin("E:/Avisynth/plugins_fred/rgtools.dll")
Loadplugin("E:/Avisynth/plugins_fred/masktools2.dll")
LoadPlugin("E:/Avisynth/plugins_fred/removedirtsse2.dll")
Loadplugin("E:/Avisynth/plugins_fred/warpsharp.dll")
LoadPlugin("E:/Avisynth/plugins_fred/fft3Dfilter.dll")
LoadPlugin("E:/Avisynth/plugins_fred/hqdn3D.dll")
Import("E:/Avisynth/plugins_fred/TemporalDegrain.avs")
LoadPlugin("E:/Avisynth/plugins_fred/GetSystemEnv.dll")
num = GetSystemEnv("NUM")
film= "E:\Magis\Deshaker\"+num+".avi"
SetMemoryMax(1024)
source= AviSource(film,audio=false).assumefps(16).converttoYV12()
cleaned= RemoveDirtMC(source,200)
denoised=cleaned.TemporalDegrain(SAD1=800,SAD2=600,degrain=3)  
sharpened=denoised.unsharpmask(30,5,0).blur(0.8).unsharpmask(50,3,0).blur(0.8).sharpen(0.1)
adjusted=source.levels(0,1.2,255,0,255).coloryuv(autowhite=true,autogain=true)
Eval("adjusted")
#left=sharpened
#right=adjusted
#compare= stackhorizontal(subtitle(left,"",size=28,align=2),subtitle(right,"",size=28,align=2))
#Eval("Compare")

```

Remarques:

num = GetSystemEnv("NUM")
permet de passer le nom du fichier dans une procédure batch (nécessite Avisynth+). Sinon mettre le nom du fichier 

cleaned et denoised
La plupart des plugins de cleaning et degrain sont plus ou moins équivalents, j'ai obtenus de bons résultats avec ceux-ci

sharpened=denoised.unsharpmask(30,5,0).blur(0.8).unsharpmask(50,3,0).blur(0.8).sharpen(0.1)
C'est une recette  de videofred  qui donne un excellent résultat, ajuster éventuellement les paramètres

adjusted=source.levels(0,1.2,255,0,255).coloryuv(autowhite=true,autogain=true)
C'est le plus délicat de trouver des réglages valables pour la totalité du film, sachant que cela peut ensuite être traité plus finement scène par scène dans l'éditeur NLE.  Pour moi la balance des blancs automatique ainsi que l'ajustement automatique des niveaux me donne un bon résultat.  Le réglage préalable du gamma à 1.2 n'est pas forcément nécessaire

Les ligne commentées en fin de script vous permettent de tester l'effet de certains paramètres

Pour exécuter, ouvrir le script dans VirtualDub et faire "Save" après avoir choisi le codec de sortie (pour moi MagicYuv)



## Automatiser le traitement par VirtualDub

En présence de nombreux films à traiter il faut pouvoir automatiser les traitements avec des procédures batch.

Pour automatiser VirtiualDub le principe est le suivant , ouvrir le script, préparer toutes les options (Codec ...) et sauvegarder les settings de Virtualdub dans un fichier vdscript, éditer ce fichier et ajouter en première ligne le nom du fichier d'entrée et en dernière le nom du fichier de sortie. Ce qui donne par exemple:  fichier cleaning.vdscript

```
VirtualDub.Open("E:/Magis/Scripts/cleaning/cleaning.avs");
VirtualDub.audio.SetSource(0);
... Tous les settings
VirtualDub.audio.filters.Clear();
VirtualDub.SaveAVI("E:/Magis/cleaned/"+VirtualDub.params[0]+".avi");
```

Alors VirtualDub peut être appelé dans une procédure batch:  cleaning.cmd

```
echo Cleaning %1
set NUM=%1
set path="C:\Applications\VirtualDub2";%path%
set vdub=vdub.exe
%vdub% /i cleaning.vdscript "%1" /x  
```

La variable d'environnement NUM, le numéro de bande, est récupérée dans le script Avisynth.
Il suffit alors appeler cleaning avec comme argument le numéro de bande, par exemple cleaning 60

Pour traiter automatiquement toutes les bandes:

```
@echo off
for %%N in (01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 31 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61) do (
	if exist e:\Magis\Deshaker\%%N.avi (
 		if not exist e:\Magis\cleaned\%%N.avi (
			call cleaning %%N
		)
	)
)
```

Lancer et revenir plusieurs heure après !

## L'éditeur NLE

L'éditeur NLE va permettre le découpage, des corrections de couleurs plus fines pour certaines scènes,  l'insertion de titres, etc...

Ici chacun aura son outil préféré, personnellement j'utilise VEGAS Pro dans une version assez ancienne 13

## Encodage final

L'encodage final avec le codec choisi peut se faire directement à partir de l'éditeur NLE.

Personnellement j'utilise du frame serving à partir de VEGAS (DebugMode Frame Server) ce qui me permet d'utiliser les excellents codec libres AVC X264 ou HEVC x265 à partir de MeGUI, le résultat étant muxé dans un conteneur  MKV. Je crois que cette solution est aussi possible avec Adobe Premiere.

Pour encoder une bande restaurée sans passer par l'éditeur NLE, utiliser directement Megui:

```
#80.avs
film= "E:\Magis\Cleaned\80.avi"
source=AviSource(film).converttoYV12(matrix="pc.601")
return source


```

et

```
echo ------------------------------%1 PASS 1
"C:\Applications\MeGui\tools\x264\x264.exe"  --preset medium --pass 1 --bitrate 2000 --stats e:\Magis\render\%1.stats  --output NUL %1.avs
echo ------------------------------%1 PASS 2
"C:\Applications\MeGui\tools\x264\x264.exe"   --preset medium  --pass 2 --bitrate 2000 --stats e:\magis\render\%1.stats  --output e:\Magis\render\%1.264 %1.avs 
"C:\Applications\MeGui\tools\mkvmerge\mkvmerge.exe" -o e:\Magis\final\MKVAVC\%1.mkv e:\Magis\render\%1.264 


```

Encodage en deux passes avec un bitrate 2000bit/s

