#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import shutil
import tempfile
import threading

import yt_dlp
import qtawesome as qta


def _find_ffmpeg_dir() -> str:
    """
    Localise un dossier contenant ffmpeg ET ffprobe.

    Priorité :
      1. Dossier du script + emplacements courants Windows (ffmpeg + ffprobe présents)
      2. PATH système
      3. ffmpeg trouvé localement + ffprobe fourni par static-ffmpeg
         → assemblage dans un dossier temporaire dédié
      4. static-ffmpeg seul (télécharge les deux binaires automatiquement)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    drive      = os.path.splitdrive(sys.executable)[0] or "C:"
    exts       = ("", ".exe")

    def _find_in(directory, name):
        for e in exts:
            p = os.path.join(directory, name + e)
            if os.path.isfile(p):
                return p
        return None

    search_dirs = [
        script_dir,
        os.path.join(script_dir, "ffmpeg", "bin"),
        os.path.join(script_dir, "ffmpeg"),
        os.path.join(drive, os.sep, "ffmpeg", "bin"),
        os.path.join(drive, os.sep, "ffmpeg"),
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "ffmpeg", "bin"),
        os.path.join(os.environ.get("USERPROFILE", ""), "ffmpeg", "bin"),
    ]

    # ── 1. Dossier local : les deux binaires présents ─────────────────────────
    for d in search_dirs:
        if _find_in(d, "ffmpeg") and _find_in(d, "ffprobe"):
            return d

    # ── 2. PATH système ───────────────────────────────────────────────────────
    ff_which = shutil.which("ffmpeg")
    fp_which = shutil.which("ffprobe")
    if ff_which and fp_which:
        return os.path.dirname(os.path.abspath(ff_which))

    # ── 3. ffmpeg local + ffprobe de static-ffmpeg → dossier temporaire ───────
    #   Cas typique : l'utilisateur a ffmpeg.exe dans le dossier du projet
    #   mais pas ffprobe.exe. On les réunit dans un dossier temp.
    ff_src = next((p for d in search_dirs if (p := _find_in(d, "ffmpeg"))), None)
    if ff_src is None and ff_which:
        ff_src = ff_which

    fp_src = None
    try:
        import static_ffmpeg
        _, fp_static = static_ffmpeg.add_paths(weak=False)
        if os.path.isfile(fp_static):
            fp_src = fp_static
    except Exception:
        pass

    if ff_src and fp_src:
        tools = os.path.join(tempfile.gettempdir(), "yt_down_tools")
        os.makedirs(tools, exist_ok=True)
        ff_dst = os.path.join(tools, "ffmpeg.exe")
        fp_dst = os.path.join(tools, "ffprobe.exe")
        if not os.path.isfile(ff_dst):
            shutil.copy2(ff_src, ff_dst)
        if not os.path.isfile(fp_dst):
            shutil.copy2(fp_src, fp_dst)
        if os.path.isfile(ff_dst) and os.path.isfile(fp_dst):
            return tools

    # ── 4. static-ffmpeg seul (fourni ffmpeg + ffprobe) ───────────────────────
    try:
        import static_ffmpeg
        ff, fp = static_ffmpeg.add_paths(weak=False)
        if os.path.isfile(ff) and os.path.isfile(fp):
            return os.path.dirname(os.path.abspath(ff))
    except Exception:
        pass

    return ""


FFMPEG_DIR = _find_ffmpeg_dir()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt, QThread, QSize, pyqtSignal
from PyQt6.QtGui import QFont

# ── Palette ──────────────────────────────────────────────────────────────────
YT_RED     = "#FF0000"
YT_DARK    = "#CC0000"
YT_DEEP    = "#990000"
BG_MAIN    = "#0F0F0F"
BG_SURFACE = "#1A1A1A"
BG_INPUT   = "#242424"
BG_HOVER   = "#2A2A2A"
C_WHITE    = "#FFFFFF"
C_GRAY     = "#AAAAAA"
C_BORDER   = "#333333"
C_GREEN    = "#00CC66"
C_ORANGE   = "#FF9500"

# ── Feuille de style QSS (syntaxe CSS Qt) ────────────────────────────────────
QSS = f"""
/* ── Fond global ── */
QMainWindow,
QWidget {{
    background-color: {BG_MAIN};
    color: {C_WHITE};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 11px;
}}

/* ── Étiquettes ── */
QLabel {{
    color: {C_WHITE};
    background: transparent;
}}
QLabel#title {{
    color: {YT_RED};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
QLabel#info {{
    color: {C_GRAY};
    font-size: 10px;
}}
QLabel#status {{
    color: {C_GRAY};
    font-size: 10px;
}}

/* ── Champs texte ── */
QLineEdit {{
    background-color: {BG_INPUT};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    padding: 4px 9px;
    selection-background-color: {YT_RED};
}}
QLineEdit:focus {{
    border: 1px solid {YT_RED};
    background-color: #1E1E1E;
}}
QLineEdit:read-only {{
    color: {C_GRAY};
}}
QLineEdit::placeholder {{
    color: #666666;
    font-style: italic;
}}

/* ── Listes déroulantes ── */
QComboBox {{
    background-color: {BG_INPUT};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    padding: 4px 9px;
    min-width: 55px;
}}
QComboBox:focus,
QComboBox:on {{
    border-color: {YT_RED};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    border: none;
}}
QComboBox::down-arrow {{
    border-left:  4px solid transparent;
    border-right: 4px solid transparent;
    border-top:   5px solid {C_GRAY};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    selection-background-color: {YT_RED};
    selection-color: {C_WHITE};
    outline: none;
    padding: 2px;
}}
QComboBox QAbstractItemView::item {{
    padding: 4px 8px;
    min-height: 22px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {YT_DARK};
}}

/* ── Bouton principal (rouge YouTube) ── */
QPushButton {{
    background-color: {YT_RED};
    color: {C_WHITE};
    border: none;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 700;
    font-size: 11px;
}}
QPushButton:hover {{
    background-color: {YT_DARK};
}}
QPushButton:pressed {{
    background-color: {YT_DEEP};
}}
QPushButton:disabled {{
    background-color: #2E2E2E;
    color: #555555;
}}

/* ── Boutons secondaires (surface sombre) ── */
QPushButton#sec {{
    background-color: {BG_SURFACE};
    border: 1px solid {C_BORDER};
    color: {C_WHITE};
    font-weight: 400;
}}
QPushButton#sec:hover {{
    background-color: {BG_HOVER};
    border-color: {YT_RED};
    color: {C_WHITE};
}}
QPushButton#sec:pressed {{
    background-color: {BG_MAIN};
    border-color: {YT_DEEP};
}}
QPushButton#sec:disabled {{
    background-color: {BG_SURFACE};
    border-color: #222222;
    color: #444444;
}}

/* ── Barre de progression ── */
QProgressBar {{
    background-color: {BG_INPUT};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    text-align: center;
    color: {C_WHITE};
    font-size: 10px;
    font-weight: 600;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #006622,
        stop:1 #00CC66
    );
    border-radius: 4px;
}}

/* ── Séparateur ── */
QFrame#sep {{
    background-color: {C_BORDER};
    max-height: 1px;
    border: none;
}}
"""

# ── Tailles des icônes Font Awesome ──────────────────────────────────────────
ICO_SM  = QSize(13, 13)
ICO_MD  = QSize(15, 15)
ICO_LG  = QSize(18, 18)

def ico(name, color=C_WHITE, size=ICO_SM):
    return qta.icon(name, color=color), size


# ── Thread de téléchargement ─────────────────────────────────────────────────
class DownloadThread(QThread):
    sig_progress = pyqtSignal(float, str, str, str)
    sig_status   = pyqtSignal(str)
    sig_done     = pyqtSignal(bool, str)

    def __init__(self, url, folder, fmt, quality, cookies):
        super().__init__()
        self.url     = url
        self.folder  = folder
        self.fmt     = fmt
        self.quality = quality
        self.cookies = cookies
        self._cancelled = False
        self._pause_evt = threading.Event()
        self._pause_evt.set()

    def pause(self):   self._pause_evt.clear()
    def resume(self):  self._pause_evt.set()
    def cancel(self):
        self._cancelled = True
        self._pause_evt.set()

    def _hook(self, d):
        if self._cancelled:
            raise Exception("annulé")
        self._pause_evt.wait()
        if self._cancelled:
            raise Exception("annulé")

        if d["status"] == "downloading":
            try:
                pct = float(d.get("_percent_str", "0%").strip().replace("%", ""))
            except ValueError:
                dl    = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct   = (dl / total * 100) if total else 0

            speed = d.get("_speed_str", "—").strip()
            size  = (d.get("_total_bytes_str") or d.get("_total_bytes_estimate_str") or "—").strip()
            eta   = d.get("_eta_str", "—").strip()
            self.sig_progress.emit(pct, speed, size, eta)
            self.sig_status.emit(f"Téléchargement… {pct:.1f}%")

        elif d["status"] == "finished":
            self.sig_status.emit("Post-traitement (FFmpeg)…")

    def _build_opts(self):
        q, postproc = self.quality, []

        if self.fmt == "MP3":
            fmt_str = "bestaudio/best"
            postproc = [{"key": "FFmpegExtractAudio",
                         "preferredcodec": "mp3", "preferredquality": "192"}]

        elif self.fmt == "WEBM":
            _map = {
                "1080p": "bestvideo[height<=1080][ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
                "720p":  "bestvideo[height<=720][ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
                "480p":  "bestvideo[height<=480][ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
                "360p":  "bestvideo[height<=360][ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
                "144p":  "bestvideo[height<=144][ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
                "Audio": "bestaudio[ext=webm]/bestaudio/best",
            }
            fmt_str = _map.get(q, "best")

        else:  # MP4
            _map = {
                "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
                "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
                "480p":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
                "360p":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best",
                "144p":  "bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=144]+bestaudio/best",
                "Audio": "bestaudio[ext=m4a]/bestaudio/best",
            }
            fmt_str = _map.get(q, "bestvideo+bestaudio/best")
            if q != "Audio":
                postproc = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]

        opts = {
            "format":              fmt_str,
            "outtmpl":             os.path.join(self.folder, "%(title)s.%(ext)s"),
            "progress_hooks":      [self._hook],
            "postprocessors":      postproc,
            "quiet":               True,
            "no_warnings":         False,
            "merge_output_format": "mp4" if self.fmt == "MP4" and q != "Audio" else None,
        }
        if FFMPEG_DIR:
            opts["ffmpeg_location"] = FFMPEG_DIR
        if self.cookies and os.path.isfile(self.cookies):
            opts["cookiefile"] = self.cookies
        return opts

    def run(self):
        try:
            with yt_dlp.YoutubeDL(self._build_opts()) as ydl:
                ydl.download([self.url])
            if not self._cancelled:
                self.sig_done.emit(True, "Téléchargement terminé avec succès !")
        except Exception as exc:
            msg = str(exc)
            if self._cancelled or "annulé" in msg.lower():
                self.sig_done.emit(False, "Téléchargement annulé.")
            else:
                self.sig_done.emit(False, f"Erreur : {msg}")


# ── Fenêtre principale ────────────────────────────────────────────────────────
class App(QMainWindow):
    _URL_RE = re.compile(
        r"(https?://)?(www\.)?"
        r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)[\w\-?=&]+"
    )

    def __init__(self):
        super().__init__()
        self._thread  : DownloadThread | None = None
        self._paused  = False
        self._dest    = os.path.expanduser("~/Downloads")
        self._cookies = ""

        self.setWindowTitle("YouTube Downloader Pro")
        self.setFixedSize(500, 350)
        self.setWindowIcon(qta.icon("fa5b.youtube", color=YT_RED))
        self.setStyleSheet(QSS)
        self._build_ui()

    # ── construction UI ───────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)

        # ── Titre ──────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setSpacing(7)

        yt_icon = QLabel()
        yt_icon.setPixmap(qta.icon("fa5b.youtube", color=YT_RED).pixmap(ICO_LG))
        title_lbl = QLabel("YouTube Downloader Pro")
        title_lbl.setObjectName("title")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))

        title_row.addWidget(yt_icon)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)

        # ── Séparateur ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        # ── Ligne 1 : Dossier ──────────────────────────────────────────────
        r1 = QHBoxLayout(); r1.setSpacing(6)
        lbl_d = QLabel("Dossier :")
        lbl_d.setFixedWidth(54)
        self.inp_folder = QLineEdit(self._dest)
        self.inp_folder.setReadOnly(True)

        btn_folder = QPushButton("  Parcourir")
        btn_folder.setObjectName("sec")
        btn_folder.setIcon(qta.icon("fa5s.folder-open", color=C_WHITE))
        btn_folder.setIconSize(ICO_SM)
        btn_folder.setFixedWidth(90)
        btn_folder.clicked.connect(self._pick_folder)

        r1.addWidget(lbl_d)
        r1.addWidget(self.inp_folder)
        r1.addWidget(btn_folder)
        lay.addLayout(r1)

        # ── Ligne 2 : URL ──────────────────────────────────────────────────
        r2 = QHBoxLayout(); r2.setSpacing(6)
        lbl_u = QLabel("URL :")
        lbl_u.setFixedWidth(54)
        self.inp_url = QLineEdit()
        self.inp_url.setPlaceholderText("Collez votre lien YouTube ici…")

        r2.addWidget(lbl_u)
        r2.addWidget(self.inp_url)
        lay.addLayout(r2)

        # ── Ligne 3 : Format / Qualité / Cookies ──────────────────────────
        r3 = QHBoxLayout(); r3.setSpacing(6)

        lbl_f = QLabel("Format :");  lbl_f.setFixedWidth(50)
        self.cmb_fmt = QComboBox()
        self.cmb_fmt.addItems(["MP4", "MP3", "WEBM"])
        self.cmb_fmt.setFixedWidth(64)

        lbl_q = QLabel("Qualité :"); lbl_q.setFixedWidth(50)
        self.cmb_qual = QComboBox()
        self.cmb_qual.addItems(["1080p", "720p", "480p", "360p", "144p", "Audio"])
        self.cmb_qual.setFixedWidth(70)

        lbl_c = QLabel("Cookies :"); lbl_c.setFixedWidth(52)
        self.inp_cookie = QLineEdit()
        self.inp_cookie.setPlaceholderText("cookies.txt")
        self.inp_cookie.setReadOnly(True)

        btn_cookie = QPushButton()
        btn_cookie.setObjectName("sec")
        btn_cookie.setIcon(qta.icon("fa5s.cookie-bite", color=C_ORANGE))
        btn_cookie.setIconSize(ICO_SM)
        btn_cookie.setFixedWidth(30)
        btn_cookie.setToolTip("Sélectionner le fichier cookies.txt")
        btn_cookie.clicked.connect(self._pick_cookies)

        r3.addWidget(lbl_f);  r3.addWidget(self.cmb_fmt)
        r3.addWidget(lbl_q);  r3.addWidget(self.cmb_qual)
        r3.addWidget(lbl_c);  r3.addWidget(self.inp_cookie); r3.addWidget(btn_cookie)
        lay.addLayout(r3)

        # ── Bouton Télécharger ─────────────────────────────────────────────
        self.btn_dl = QPushButton("  Télécharger")
        self.btn_dl.setIcon(qta.icon("fa5s.download", color=C_WHITE))
        self.btn_dl.setIconSize(ICO_MD)
        self.btn_dl.setFixedHeight(32)
        self.btn_dl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_dl.clicked.connect(self._start)
        lay.addWidget(self.btn_dl)

        # ── Barre de progression ───────────────────────────────────────────
        self.prog = QProgressBar()
        self.prog.setValue(0)
        self.prog.setFixedHeight(18)
        self.prog.setFormat("%p%")
        lay.addWidget(self.prog)

        # ── Infos vitesse / taille / eta ───────────────────────────────────
        self.lbl_info = QLabel("Vitesse : —  |  Taille : —  |  Temps restant : —")
        self.lbl_info.setObjectName("info")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_info)

        # ── Boutons contrôle ───────────────────────────────────────────────
        r5 = QHBoxLayout(); r5.setSpacing(6)

        self.btn_pause = QPushButton("  Pause")
        self.btn_pause.setObjectName("sec")
        self.btn_pause.setIcon(qta.icon("fa5s.pause", color=C_WHITE))
        self.btn_pause.setIconSize(ICO_SM)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._toggle_pause)

        self.btn_cancel = QPushButton("  Annuler")
        self.btn_cancel.setObjectName("sec")
        self.btn_cancel.setIcon(qta.icon("fa5s.times-circle", color=YT_RED))
        self.btn_cancel.setIconSize(ICO_SM)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)

        self.btn_clear = QPushButton("  Effacer")
        self.btn_clear.setObjectName("sec")
        self.btn_clear.setIcon(qta.icon("fa5s.trash-alt", color=C_GRAY))
        self.btn_clear.setIconSize(ICO_SM)
        self.btn_clear.clicked.connect(self._clear)

        r5.addWidget(self.btn_pause)
        r5.addWidget(self.btn_cancel)
        r5.addWidget(self.btn_clear)
        lay.addLayout(r5)

        # ── Barre de statut ────────────────────────────────────────────────
        status_row = QHBoxLayout(); status_row.setSpacing(5)
        self.ico_status = QLabel()
        self.ico_status.setPixmap(
            qta.icon("fa5s.circle", color="#444444").pixmap(QSize(8, 8))
        )
        self.lbl_status = QLabel("Prêt à télécharger")
        self.lbl_status.setObjectName("status")
        self.lbl_status.setWordWrap(True)

        status_row.addStretch()
        status_row.addWidget(self.ico_status)
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        lay.addLayout(status_row)

    # ── slots ──────────────────────────────────────────────────────────────────
    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Dossier de destination", self._dest)
        if d:
            self._dest = d
            self.inp_folder.setText(d)

    def _pick_cookies(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Fichier cookies", "", "Fichiers texte (*.txt);;Tous (*)"
        )
        if f:
            self._cookies = f
            self.inp_cookie.setText(os.path.basename(f))

    def _set_status(self, msg, color=C_GRAY, icon_name="fa5s.circle", icon_color="#555555"):
        self.lbl_status.setStyleSheet(f"color: {color}; font-size: 10px;")
        self.lbl_status.setText(msg)
        self.ico_status.setPixmap(
            qta.icon(icon_name, color=icon_color).pixmap(QSize(8, 8))
        )

    def _start(self):
        url = self.inp_url.text().strip()
        if not url:
            self._set_status("Veuillez entrer une URL YouTube.", C_ORANGE,
                             "fa5s.exclamation-triangle", C_ORANGE); return
        if not self._URL_RE.match(url):
            self._set_status("URL YouTube invalide.", C_ORANGE,
                             "fa5s.exclamation-triangle", C_ORANGE); return
        if not os.path.isdir(self._dest):
            self._set_status("Le dossier de destination n'existe pas.", C_ORANGE,
                             "fa5s.exclamation-triangle", C_ORANGE); return

        self.btn_dl.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self._paused = False
        self._set_pause_icon(False)
        self.prog.setValue(0)
        self._set_status("Démarrage…", C_GRAY, "fa5s.spinner", C_GRAY)

        self._thread = DownloadThread(
            url, self._dest,
            self.cmb_fmt.currentText(),
            self.cmb_qual.currentText(),
            self._cookies or None,
        )
        self._thread.sig_progress.connect(self._on_progress)
        self._thread.sig_status.connect(self._on_status)
        self._thread.sig_done.connect(self._on_done)
        self._thread.start()

    def _on_progress(self, pct, speed, size, eta):
        self.prog.setValue(int(pct))
        self.lbl_info.setText(f"Vitesse : {speed}  |  Taille : {size}  |  Temps restant : {eta}")

    def _on_status(self, msg):
        self._set_status(msg, C_GRAY, "fa5s.spinner", C_GRAY)

    def _on_done(self, ok, msg):
        self.btn_dl.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self._paused = False
        self._set_pause_icon(False)
        if ok:
            self.prog.setValue(100)
            self._set_status(msg, C_GREEN, "fa5s.check-circle", C_GREEN)
        else:
            if "annulé" in msg.lower():
                self._set_status(msg, C_ORANGE, "fa5s.ban", C_ORANGE)
            else:
                self._set_status(msg, YT_RED, "fa5s.times-circle", YT_RED)

    def _toggle_pause(self):
        if not self._thread:
            return
        if self._paused:
            self._thread.resume()
            self._paused = False
            self._set_pause_icon(False)
            self._set_status("Téléchargement repris…", C_GRAY, "fa5s.spinner", C_GRAY)
        else:
            self._thread.pause()
            self._paused = True
            self._set_pause_icon(True)
            self._set_status("En pause…", C_ORANGE, "fa5s.pause-circle", C_ORANGE)

    def _set_pause_icon(self, paused: bool):
        if paused:
            self.btn_pause.setIcon(qta.icon("fa5s.play", color=C_GREEN))
            self.btn_pause.setText("  Reprendre")
        else:
            self.btn_pause.setIcon(qta.icon("fa5s.pause", color=C_WHITE))
            self.btn_pause.setText("  Pause")
        self.btn_pause.setIconSize(ICO_SM)

    def _cancel(self):
        if self._thread:
            self._thread.cancel()
            self._set_status("Annulation en cours…", C_ORANGE, "fa5s.ban", C_ORANGE)

    def _clear(self):
        if self._thread and self._thread.isRunning():
            return
        self.inp_url.clear()
        self.inp_cookie.clear()
        self._cookies = ""
        self.prog.setValue(0)
        self.lbl_info.setText("Vitesse : —  |  Taille : —  |  Temps restant : —")
        self._set_status("Prêt à télécharger", C_GRAY, "fa5s.circle", "#444444")


# ── Point d'entrée ────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = App()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
