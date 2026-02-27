# YouTube Downloader Pro

Application de bureau Python permettant de télécharger des vidéos et de l'audio depuis YouTube, avec une interface graphique moderne aux couleurs de YouTube (rouge / noir / blanc).

---

## Aperçu

| Élément | Détail |
|---|---|
| Langage | Python 3.x |
| Interface | Tkinter + ttk |
| Moteur de téléchargement | yt-dlp |
| Encodage / fusion | ffmpeg (via imageio-ffmpeg) |
| Taille de la fenêtre | 500 × 350 px (fixe, centrée) |

---

## Prérequis

```bash
pip install yt-dlp imageio-ffmpeg
```

> `imageio-ffmpeg` embarque automatiquement un binaire ffmpeg — aucune installation système nécessaire.

---

## Lancement

```bash
python youtube_downloader_pro.py
```

---

## Interface utilisateur

```
┌─────────────────────────────────────────────────────┐
│ ▶  YouTube Downloader Pro              [en-tête rouge]│
├─────────────────────────────────────────────────────┤
│ 📁 Dossier  [ ~/Downloads/...............] 🍪 Cookie │
│ URL : [ coller l'URL YouTube ici          ]  ✕       │
│ Format : [MP4▾]  Qualité : [720p▾]   [⬇ Télécharger]│
│ ████████████████░░░░░░░░░░░░░░░░  ← barre verte      │
│ Vitesse : 2.4 MB/s │ 12.3 MB / 80.1 MB │ ETA : 28s  │
│ [⏸ Pause]  [✕ Annuler]  [🗑 Effacer]                │
└─────────────────────────────────────────────────────┘
```

### Contrôles

| Bouton | Rôle |
|---|---|
| **📁 Dossier** | Choisir le dossier de destination (défaut : `~/Downloads`) |
| **🍪 Cookie** | Charger un fichier de cookies `.txt` (utile pour les vidéos privées ou avec âge restreint) |
| **✕** (URL) | Vider le champ URL |
| **⬇ Télécharger** | Lancer le téléchargement |
| **⏸ Pause / ▶ Reprendre** | Mettre en pause ou reprendre le téléchargement en cours |
| **✕ Annuler** | Annuler le téléchargement (confirmation demandée) |
| **🗑 Effacer** | Remettre l'interface à zéro |

---

## Formats et qualités disponibles

### Formats

| Format | Description |
|---|---|
| **MP4** | Vidéo H.264 + audio AAC, fusionnés en `.mp4` via ffmpeg |
| **MP3** | Audio uniquement, converti en `.mp3` 192 kbps via ffmpeg |
| **WEBM** | Vidéo VP9 + audio Opus en `.webm` |

### Qualités vidéo

| Qualité | Résolution max |
|---|---|
| 1080p | 1920 × 1080 |
| 720p | 1280 × 720 *(défaut)* |
| 480p | 854 × 480 |
| 360p | 640 × 360 |
| 144p | 256 × 144 |
| Audio | Meilleure piste audio disponible |

> Sélectionner **MP3** ou **Audio** ignore le réglage de qualité vidéo et télécharge uniquement l'audio.

---

## Comportement selon la disponibilité de ffmpeg

| ffmpeg | MP4 / WEBM | MP3 / Audio |
|---|---|---|
| Disponible | Fusion vidéo + audio → meilleure qualité | Conversion en `.mp3` 192 kbps |
| Absent | Format pré-fusionné (qualité réduite) | Audio dans son format d'origine (`.webm` ou `.m4a`) |

Un avertissement s'affiche automatiquement si ffmpeg n'est pas détecté.

---

## Fichier de cookies

Certaines vidéos (âge restreint, membres, privées) nécessitent d'être authentifié. Pour cela :

1. Exporter vos cookies YouTube depuis votre navigateur au format `Netscape` (extension **Get cookies.txt LOCALLY** recommandée).
2. Cliquer sur **🍪 Cookie** et sélectionner le fichier `.txt` exporté.
3. Le bouton passe en vert pour confirmer le chargement.

---

## Architecture du code

```
youtube_downloader_pro.py
│
├── _fmt_bytes(n)          Formate une taille en octets (B, KB, MB…)
├── _fmt_speed(bps)        Formate une vitesse en octets/s
├── _fmt_eta(s)            Formate un temps restant (s, m, h)
├── _Cancelled             Exception interne pour signaler une annulation
│
└── class App
    ├── __init__           Initialisation, variables d'état, threads
    ├── _center()          Centre la fenêtre à l'écran
    ├── _styles()          Configure les styles ttk (barre verte, combobox sombre)
    ├── _btn() / _lbl()    Factories de widgets (boutons / labels stylisés)
    ├── _build()           Construction complète de l'interface
    │
    ├── pick_folder()      Sélection du dossier de destination
    ├── pick_cookie()      Sélection du fichier de cookies
    ├── start_dl()         Validation et lancement du thread de téléchargement
    ├── toggle_pause()     Pause / reprise via threading.Event
    ├── cancel_dl()        Annulation propre du téléchargement
    ├── clear()            Remise à zéro de l'interface
    │
    ├── _build_opts()      Construction du dictionnaire d'options yt-dlp
    ├── _download(url)     Thread worker : appel yt-dlp.download()
    ├── _hook(d)           Hook de progression yt-dlp (pause, annulation, UI)
    ├── _upd()             Mise à jour de la barre et des labels
    ├── _done()            Fin de téléchargement réussie
    └── _err(msg)          Affichage d'une erreur
```

---

## Gestion des erreurs

| Situation | Comportement |
|---|---|
| `yt-dlp` non installé | Message d'erreur avec la commande `pip` à lancer |
| URL invalide | Alerte avec exemple d'URL correcte |
| ffmpeg absent | Avertissement + fallback sur format pré-fusionné |
| Erreur réseau / YouTube | Boîte de dialogue avec le message d'erreur complet |
| Annulation utilisateur | Arrêt propre du thread, remise à zéro de l'interface |

---

## Palette de couleurs

| Constante | Hex | Usage |
|---|---|---|
| `RED` | `#FF0000` | En-tête, bouton Télécharger, curseur URL |
| `DRED` | `#CC0000` | Rouge foncé (ombres) |
| `BG` | `#0F0F0F` | Fond principal |
| `BG2` | `#1C1C1C` | Fond des champs et panneaux d'info |
| `BG3` | `#2D2D2D` | Fond des boutons secondaires |
| `WHITE` | `#FFFFFF` | Texte principal |
| `LG` | `#CCCCCC` | Texte secondaire |
| `MG` | `#888888` | Texte discret |
| `GREEN` | `#00C853` | Barre de progression, icône cookie chargé |
