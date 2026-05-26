# Lecteur vidéo avec visualisation des détections GCC-Net
# Usage : python tools/view_detections.py detections.csv [--video /chemin/video.mp4]

import argparse
import os.path as osp
import tkinter as tk
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk


SLIDER_H    = 28
MARK_W      = 2
CURSOR_R    = 7
BAR_H       = 6
BTN_STYLE   = dict(bg='#333', fg='white', activebackground='#555',
                   activeforeground='white', relief=tk.FLAT,
                   font=('Helvetica', 13), bd=0, padx=8, pady=4)


def parse_args():
    parser = argparse.ArgumentParser(description='Lecteur vidéo avec détections GCC-Net')
    parser.add_argument('csv',    help='Fichier CSV issu de inf_video.py')
    parser.add_argument('--video', default=None, help='Chemin vidéo (écrase celui du CSV)')
    parser.add_argument('--classes', type=int, nargs='+', default=None, metavar='CLASS_ID',
                        help='Ne garder que ces class_id (ex: --classes 3  ou  --classes 1 3 5)')
    return parser.parse_args()


def read_csv(csv_path, allowed_classes=None):
    """Retourne (video_path, liste triée de frame_idx avec détection).

    allowed_classes : set d'int ou None (= toutes les classes).
    """
    video_path      = None
    detected_frames = set()

    with open(csv_path, newline='') as f:
        for line in f:
            if line.startswith('# video_path:'):
                video_path = line.split(':', 1)[1].strip()
                continue
            if line.startswith('#') or line.startswith('frame_idx'):
                continue
            row = line.strip().split(',')
            if len(row) < 3:
                continue
            try:
                frame_idx = int(row[0])
                class_id  = int(row[2])
            except ValueError:
                continue
            if allowed_classes is None or class_id in allowed_classes:
                detected_frames.add(frame_idx)

    return video_path, sorted(detected_frames)


class DetectionSlider(tk.Canvas):
    """Slider personnalisé avec traits rouges aux positions de détection."""

    def __init__(self, parent, total_frames, detected_frames, on_seek, **kwargs):
        super().__init__(parent, height=SLIDER_H, bg='#1a1a1a',
                         highlightthickness=0, **kwargs)
        self.total_frames    = max(total_frames, 1)
        self.detected_frames = detected_frames
        self.on_seek         = on_seek
        self.current_frame   = 0

        self.bind('<Configure>',     self._redraw)
        self.bind('<ButtonPress-1>', self._on_click)
        self.bind('<B1-Motion>',     self._on_drag)

    def set_frame(self, frame_idx):
        self.current_frame = frame_idx
        self._redraw()

    def _x_from_frame(self, frame_idx):
        return int(frame_idx / self.total_frames * self.winfo_width())

    def _frame_from_x(self, x):
        w = self.winfo_width()
        return max(0, min(int(x / w * self.total_frames), self.total_frames - 1))

    def _redraw(self, _event=None):
        w   = self.winfo_width()
        h   = SLIDER_H
        mid = h // 2
        self.delete('all')

        # Barre de fond
        self.create_rectangle(0, mid - BAR_H // 2, w, mid + BAR_H // 2,
                               fill='#444', outline='')

        # Barre de progression
        x_pos = self._x_from_frame(self.current_frame)
        self.create_rectangle(0, mid - BAR_H // 2, x_pos, mid + BAR_H // 2,
                               fill='#888', outline='')

        # Traits rouges aux détections
        for f in self.detected_frames:
            x = self._x_from_frame(f)
            self.create_line(x, 0, x, h, fill='red', width=MARK_W)

        # Curseur blanc
        self.create_oval(x_pos - CURSOR_R, mid - CURSOR_R,
                         x_pos + CURSOR_R, mid + CURSOR_R,
                         fill='white', outline='')

    def _on_click(self, event):
        self.on_seek(self._frame_from_x(event.x))

    def _on_drag(self, event):
        self.on_seek(self._frame_from_x(event.x))


class VideoPlayer:

    def __init__(self, root, video_path, detected_frames):
        self.root            = root
        self.detected_frames = detected_frames  # liste triée
        self._after_id       = None
        self.playing         = False
        self._last_frame_bgr = None             # pour le re-render au resize

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            messagebox.showerror('Erreur', f'Impossible d\'ouvrir la vidéo :\n{video_path}')
            root.destroy()
            return

        self.fps          = self.cap.get(cv2.CAP_PROP_FPS) or 25
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_delay  = int(1000 / self.fps)
        self.current_frame = 0

        self._build_ui(video_path)
        # Délai pour que le canvas ait sa taille finale avant le premier rendu
        root.after(50, lambda: self._seek(0))

        root.bind('<space>',  lambda e: self._toggle_play())
        root.bind('<Left>',   lambda e: self._seek(max(0, self.current_frame - 1)))
        root.bind('<Right>',  lambda e: self._seek(min(self.total_frames - 1, self.current_frame + 1)))
        root.bind('<Prior>',  lambda e: self._prev_detection())  # Page Up
        root.bind('<Next>',   lambda e: self._next_detection())  # Page Down
        root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self, video_path):
        self.root.title(f'Détections — {osp.basename(video_path)}')
        self.root.configure(bg='#111')

        # Layout en grille : ligne 0 (vidéo) s'étire, lignes 1-2 restent fixes
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        # --- Zone vidéo (row 0) : Canvas qui garde sa taille indépendamment ---
        self.canvas_video = tk.Canvas(self.root, bg='black', highlightthickness=0)
        self.canvas_video.grid(row=0, column=0, sticky='nsew', padx=4, pady=4)
        self.canvas_video.bind('<Configure>', self._on_video_resize)

        # --- Slider (row 1) ---
        self.slider = DetectionSlider(
            self.root, self.total_frames, self.detected_frames,
            on_seek=self._seek_and_pause)
        self.slider.grid(row=1, column=0, sticky='ew', padx=8, pady=(0, 4))

        # --- Barre de contrôles (row 2) ---
        bar = tk.Frame(self.root, bg='#1a1a1a')
        bar.grid(row=2, column=0, sticky='ew', padx=8, pady=(4, 8))

        # Bouton << détection précédente
        tk.Button(bar, text='⏮ Préc.', command=self._prev_detection,
                  **BTN_STYLE).pack(side=tk.LEFT, padx=(0, 4), fill=tk.Y)

        # Bouton play/pause
        self.btn_play = tk.Button(bar, text='▶', width=3,
                                   command=self._toggle_play, **BTN_STYLE)
        self.btn_play.pack(side=tk.LEFT, padx=(0, 4), fill=tk.Y)

        # Bouton >> détection suivante
        tk.Button(bar, text='Suiv. ⏭', command=self._next_detection,
                  **BTN_STYLE).pack(side=tk.LEFT, padx=(0, 12), fill=tk.Y)

        # Timecode
        self.lbl_time = tk.Label(bar, text='00:00.000 / 00:00.000',
                                  bg='#1a1a1a', fg='white',
                                  font=('Courier', 11))
        self.lbl_time.pack(side=tk.LEFT, fill=tk.Y)

        n = len(self.detected_frames)
        tk.Label(bar, text=f'{n} détection(s)',
                 bg='#1a1a1a', fg='#ff4444',
                 font=('Helvetica', 11)).pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------
    # Navigation entre détections
    # ------------------------------------------------------------------

    def _next_detection(self):
        if not self.detected_frames:
            return
        for f in self.detected_frames:
            if f > self.current_frame:
                self._seek_and_pause(f)
                return
        self._seek_and_pause(self.detected_frames[0])   # wraparound → première

    def _prev_detection(self):
        if not self.detected_frames:
            return
        for f in reversed(self.detected_frames):
            if f < self.current_frame:
                self._seek_and_pause(f)
                return
        self._seek_and_pause(self.detected_frames[-1])  # wraparound → dernière

    # ------------------------------------------------------------------
    # Lecture / seek
    # ------------------------------------------------------------------

    def _seek_and_pause(self, frame_idx):
        self._stop_playback()
        self.btn_play.config(text='▶')
        self._seek(frame_idx)

    def _seek(self, frame_idx):
        self.current_frame = frame_idx
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()
        if ret:
            self._last_frame_bgr = frame
            self._show_frame(frame)
        self.slider.set_frame(frame_idx)
        self._update_timecode()

    def _toggle_play(self):
        if self.playing:
            self._stop_playback()
            self.btn_play.config(text='▶')
        else:
            self.playing = True
            self.btn_play.config(text='⏸')
            self._play_loop()

    def _stop_playback(self):
        self.playing = False
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def _play_loop(self):
        if not self.playing:
            return
        ret, frame = self.cap.read()
        if not ret:
            self._stop_playback()
            self.btn_play.config(text='▶')
            return
        self.current_frame   = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        self._last_frame_bgr = frame
        self._show_frame(frame)
        self.slider.set_frame(self.current_frame)
        self._update_timecode()
        self._after_id = self.root.after(self.frame_delay, self._play_loop)

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------

    def _on_video_resize(self, event):
        if self._last_frame_bgr is not None:
            self._show_frame(self._last_frame_bgr)

    def _show_frame(self, frame):
        w = self.canvas_video.winfo_width()
        h = self.canvas_video.winfo_height()
        if w < 2 or h < 2:
            return
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        # Redimensionner en conservant le ratio (upscale ET downscale)
        iw, ih = img.size
        scale = min(w / iw, h / ih)
        img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
        imgtk = ImageTk.PhotoImage(img)
        self.canvas_video.imgtk = imgtk   # éviter le garbage collect
        self.canvas_video.delete('all')
        self.canvas_video.create_image(w // 2, h // 2, anchor='center', image=imgtk)

    def _update_timecode(self):
        def fmt(f):
            s = f / self.fps
            return f"{int(s // 60):02d}:{s % 60:06.3f}"
        self.lbl_time.config(
            text=f"{fmt(self.current_frame)} / {fmt(self.total_frames)}")

    def _on_close(self):
        self._stop_playback()
        self.cap.release()
        self.root.destroy()


def main():
    args = parse_args()

    if not osp.isfile(args.csv):
        print(f"[ERREUR] CSV introuvable : {args.csv}")
        return

    allowed_classes = set(args.classes) if args.classes else None
    video_path, detected_frames = read_csv(args.csv, allowed_classes)

    if args.video:
        video_path = args.video

    if not video_path or not osp.isfile(video_path):
        print(f"[ERREUR] Vidéo introuvable : {video_path}")
        print("Utilisez --video pour spécifier le chemin manuellement.")
        return

    print(f"[INFO] Vidéo      : {video_path}")
    if allowed_classes:
        print(f"[INFO] Classes    : {sorted(allowed_classes)}")
    print(f"[INFO] Détections : {len(detected_frames)} frame(s)")

    root = tk.Tk()
    root.geometry('1280x760')
    VideoPlayer(root, video_path, detected_frames)
    root.mainloop()


if __name__ == '__main__':
    main()
