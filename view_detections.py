# Lecteur vidéo avec visualisation des détections GCC-Net
# Usage : python view_detections.py detections.csv [--video /chemin/video.mp4]

import argparse
import bisect
import os.path as osp
import tkinter as tk
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk


SLIDER_H  = 28
MARK_W    = 2
CURSOR_R  = 7
BAR_H     = 6
BTN_STYLE = dict(bg='#333', fg='white', activebackground='#555',
                 activeforeground='white', relief=tk.FLAT,
                 font=('Helvetica', 13), bd=0, padx=8, pady=4)

CLASS_NAMES = {
    0: "Squid",
    1: "Sardine",
    2: "Ray",
    3: "Sunfish",
    4: "Pilot Fish",
    5: "Shark",
    6: "JellyFish",
    7: "Tuna",
    8: "Mackerel",
}

CLASS_COLORS = {
    0: "#E040FB",  # Squid      - violet
    1: "#FFEB3B",  # Sardine    - jaune vif
    2: "#66BB6A",  # Ray        - vert
    3: "#FFA726",  # Sunfish    - orange
    4: "#FF4081",  # Pilot Fish - rose vif
    5: "#EF5350",  # Shark      - rouge
    6: "#CE93D8",  # JellyFish  - mauve clair
    7: "#FF7043",  # Tuna       - orange foncé
    8: "#8BC34A",  # Mackerel   - vert lime
}


def parse_args():
    parser = argparse.ArgumentParser(description='Lecteur vidéo avec détections GCC-Net')
    parser.add_argument('csv', help='Fichier CSV issu de inf_video.py')
    parser.add_argument('--video', default=None, help='Chemin vidéo (écrase celui du CSV)')
    parser.add_argument('--classes', type=int, nargs='+', default=None, metavar='CLASS_ID',
                        help='Classes initialement visibles (ex: --classes 3  ou  --classes 1 3 5)')
    return parser.parse_args()


def read_csv(csv_path):
    """Retourne (video_path, detections_by_class).

    detections_by_class : {class_id (int): {frame_idx (int): max_score (float)}}
    """
    video_path = None
    detections_by_class = {}

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
            try:
                score = float(row[4]) if len(row) > 4 else 1.0
            except ValueError:
                score = 1.0
            frames = detections_by_class.setdefault(class_id, {})
            frames[frame_idx] = max(frames.get(frame_idx, 0.0), score)

    return video_path, detections_by_class


def frames_union(detections_by_class, visible_classes):
    """Liste triée des frames ayant au moins une détection parmi les classes visibles."""
    frames = set()
    for cls_id in visible_classes:
        frames.update(detections_by_class.get(cls_id, set()))
    return sorted(frames)


class DetectionSlider(tk.Canvas):
    """Slider avec traits colorés par classe aux positions de détection."""

    def __init__(self, parent, total_frames, detections_by_class, visible_classes, on_seek, **kwargs):
        super().__init__(parent, height=SLIDER_H, bg='#1a1a1a',
                         highlightthickness=0, **kwargs)
        self.total_frames        = max(total_frames, 1)
        self.detections_by_class = detections_by_class
        self.visible_classes     = set(visible_classes)
        self.on_seek             = on_seek
        self.current_frame       = 0
        self._detected_frames    = frames_union(detections_by_class, visible_classes)

        self.bind('<Configure>',     self._redraw)
        self.bind('<ButtonPress-1>', self._on_click)
        self.bind('<B1-Motion>',     self._on_drag)

    @property
    def detected_frames(self):
        return self._detected_frames

    def set_detections(self, detections_by_class):
        """Remplace les détections (déjà filtrées) et redessine."""
        self.detections_by_class = detections_by_class
        self.visible_classes     = set(detections_by_class.keys())
        self._detected_frames    = frames_union(detections_by_class, self.visible_classes)
        self._redraw()

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

        # Traits colorés par classe (ordre croissant pour superposition cohérente)
        for cls_id in sorted(self.visible_classes):
            color = CLASS_COLORS.get(cls_id, '#ff4444')
            for f in self.detections_by_class.get(cls_id, set()):
                x = self._x_from_frame(f)
                self.create_line(x, 0, x, h, fill=color, width=MARK_W)

        # Curseur blanc
        self.create_oval(x_pos - CURSOR_R, mid - CURSOR_R,
                         x_pos + CURSOR_R, mid + CURSOR_R,
                         fill='white', outline='')

    def _on_click(self, event):
        self.on_seek(self._frame_from_x(event.x))

    def _on_drag(self, event):
        self.on_seek(self._frame_from_x(event.x))


class VideoPlayer:

    def __init__(self, root, video_path, detections_by_class, initial_classes=None):
        self.root                = root
        self.detections_by_class = detections_by_class
        self._after_id           = None
        self.playing             = False
        self._last_frame_bgr     = None

        det_classes = set(detections_by_class.keys())
        if initial_classes is not None:
            self._class_visible = {cid: (cid in initial_classes) for cid in det_classes}
        else:
            self._class_visible = {cid: True for cid in det_classes}

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            messagebox.showerror('Erreur', f'Impossible d\'ouvrir la vidéo :\n{video_path}')
            root.destroy()
            return

        self.fps              = self.cap.get(cv2.CAP_PROP_FPS) or 25
        self.total_frames     = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_delay      = int(1000 / self.fps)
        self.current_frame    = 0
        self._conf_threshold  = 0.0
        self._nav_lock        = False  # empêche les navigations imbriquées
        self._updating        = False  # empêche root.update() récursif

        self._build_ui(video_path)
        root.after(50, lambda: self._seek(0))

        root.bind('<space>',  lambda e: self._toggle_play())
        root.bind('<Left>',   lambda e: self._seek(max(0, self.current_frame - 1)))
        root.bind('<Right>',  lambda e: self._seek(min(self.total_frames - 1, self.current_frame + 1)))
        root.bind('<Prior>',  lambda e: self._prev_detection())
        root.bind('<Next>',   lambda e: self._next_detection())
        root.bind('a',        lambda e: self._prev_detection(1)  if not self._is_typing() else None)
        root.bind('e',        lambda e: self._next_detection(1)  if not self._is_typing() else None)
        root.bind('q',        lambda e: self._prev_detection(10) if not self._is_typing() else None)
        root.bind('d',        lambda e: self._next_detection(10) if not self._is_typing() else None)
        root.bind('<Escape>', lambda e: self._on_close())
        root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _visible_set(self):
        return {cid for cid, v in self._class_visible.items() if v}

    def _build_ui(self, video_path):
        self.root.title(f'Détections — {osp.basename(video_path)}')
        self.root.configure(bg='#111')

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_rowconfigure(3, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        # --- Zone vidéo (row 0) ---
        self.canvas_video = tk.Canvas(self.root, bg='black', highlightthickness=0)
        self.canvas_video.grid(row=0, column=0, sticky='nsew', padx=4, pady=4)
        self.canvas_video.bind('<Configure>', self._on_video_resize)

        # --- Slider (row 1) ---
        filtered = self._filtered_detections()
        self.slider = DetectionSlider(
            self.root, self.total_frames, filtered,
            set(filtered.keys()), on_seek=self._seek_and_pause)
        self.slider.grid(row=1, column=0, sticky='ew', padx=8, pady=(0, 4))

        # --- Barre de contrôles (row 2) ---
        bar = tk.Frame(self.root, bg='#1a1a1a')
        bar.grid(row=2, column=0, sticky='ew', padx=8, pady=(4, 4))

        tk.Button(bar, text='⏮ Préc.', command=self._prev_detection,
                  **BTN_STYLE).pack(side=tk.LEFT, padx=(0, 4), fill=tk.Y)

        self.btn_play = tk.Button(bar, text='▶', width=3,
                                   command=self._toggle_play, **BTN_STYLE)
        self.btn_play.pack(side=tk.LEFT, padx=(0, 4), fill=tk.Y)

        tk.Button(bar, text='Suiv. ⏭', command=self._next_detection,
                  **BTN_STYLE).pack(side=tk.LEFT, padx=(0, 12), fill=tk.Y)

        self.lbl_time = tk.Label(bar, text='00:00.000 / 00:00.000',
                                  bg='#1a1a1a', fg='white',
                                  font=('Courier', 11))
        self.lbl_time.pack(side=tk.LEFT, fill=tk.Y)

        n = len(self.slider.detected_frames)
        self.lbl_det = tk.Label(bar, text=f'{n} détection(s)',
                                 bg='#1a1a1a', fg='#ff4444',
                                 font=('Helvetica', 11))
        self.lbl_det.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Panneau filtres par classe (row 3) ---
        self._build_class_panel()

    def _build_class_panel(self):
        panel = tk.Frame(self.root, bg='#1a1a1a')
        panel.grid(row=3, column=0, sticky='ew', padx=8, pady=(0, 8))

        tk.Label(panel, text='Classes :', bg='#1a1a1a', fg='#aaa',
                 font=('Helvetica', 10)).pack(side=tk.LEFT, padx=(0, 6))

        # Slider de confiance (côté droit)
        self.var_conf = tk.StringVar(value='0.00')
        self.entry_conf = tk.Entry(panel, textvariable=self.var_conf, width=5,
                                    bg='#222', fg='white', insertbackground='white',
                                    font=('Courier', 10), justify='center',
                                    relief=tk.FLAT, bd=1)
        self.entry_conf.pack(side=tk.RIGHT, padx=(0, 4))
        self.entry_conf.bind('<Return>',   self._on_conf_entry)
        self.entry_conf.bind('<FocusOut>', self._on_conf_entry)

        self.scale_conf = tk.Scale(
            panel, from_=0.0, to=1.0, resolution=0.01,
            orient=tk.HORIZONTAL, length=160,
            bg='#1a1a1a', fg='white', highlightthickness=0,
            troughcolor='#444', activebackground='#666',
            showvalue=False, command=self._on_conf_change)
        self.scale_conf.set(0.0)
        self.scale_conf.pack(side=tk.RIGHT, padx=(4, 0))

        tk.Label(panel, text='Confiance ≥', bg='#1a1a1a', fg='#aaa',
                 font=('Helvetica', 10)).pack(side=tk.RIGHT, padx=(12, 4))

        self._class_buttons = {}
        # N'affiche que les classes présentes dans le CSV
        for cls_id in sorted(self.detections_by_class.keys()):
            cls_name   = CLASS_NAMES.get(cls_id, f'Class {cls_id}')
            is_visible = self._class_visible.get(cls_id, True)
            color = CLASS_COLORS.get(cls_id, '#999999') if is_visible else '#333'
            fg    = 'black' if is_visible else '#888'
            btn = tk.Button(
                panel,
                text=cls_name,
                bg=color, fg=fg,
                activebackground=color, activeforeground=fg,
                relief=tk.FLAT,
                font=('Helvetica', 10, 'bold'),
                bd=0, padx=6, pady=3,
                command=lambda cid=cls_id: self._toggle_class(cid),
            )
            btn.pack(side=tk.LEFT, padx=2)
            self._class_buttons[cls_id] = btn

    def _toggle_class(self, cls_id):
        self._class_visible[cls_id] = not self._class_visible[cls_id]
        is_visible = self._class_visible[cls_id]
        color = CLASS_COLORS.get(cls_id, '#999999') if is_visible else '#333'
        fg    = 'black' if is_visible else '#888'
        btn   = self._class_buttons[cls_id]
        btn.config(bg=color, fg=fg, activebackground=color, activeforeground=fg)

        self._refresh_slider()

    def _filtered_detections(self):
        """Retourne {class_id: set(frame_idx)} selon visibilité et seuil de confiance."""
        result = {}
        for cls_id, frames_scores in self.detections_by_class.items():
            if self._class_visible.get(cls_id, True):
                filtered = {f for f, s in frames_scores.items() if s >= self._conf_threshold}
                if filtered:
                    result[cls_id] = filtered
        return result

    def _refresh_slider(self):
        self.slider.set_detections(self._filtered_detections())
        self.lbl_det.config(text=f'{len(self.slider.detected_frames)} détection(s)')

    def _on_conf_change(self, value):
        self._conf_threshold = float(value)
        self.var_conf.set(f'{self._conf_threshold:.2f}')
        self._refresh_slider()

    def _on_conf_entry(self, event=None):
        try:
            val = max(0.0, min(1.0, float(self.var_conf.get())))
        except ValueError:
            val = self._conf_threshold
        self._conf_threshold = val
        self.var_conf.set(f'{val:.2f}')
        self.scale_conf.set(val)
        self._refresh_slider()
        self.root.focus_set()  # rend le focus à la fenêtre pour que les touches marchent

    def _is_typing(self):
        return isinstance(self.root.focus_get(), tk.Entry)

    # ------------------------------------------------------------------
    # Navigation entre détections
    # ------------------------------------------------------------------

    def _next_detection(self, step=1):
        if self._nav_lock:
            return
        detected = self.slider.detected_frames
        if not detected:
            return
        self._nav_lock = True
        try:
            i = bisect.bisect_right(detected, self.current_frame)
            self._seek_and_pause(detected[(i + step - 1) % len(detected)])
        finally:
            self._nav_lock = False

    def _prev_detection(self, step=1):
        if self._nav_lock:
            return
        detected = self.slider.detected_frames
        if not detected:
            return
        self._nav_lock = True
        try:
            i = bisect.bisect_left(detected, self.current_frame)
            self._seek_and_pause(detected[(i - step) % len(detected)])
        finally:
            self._nav_lock = False

    # ------------------------------------------------------------------
    # Lecture / seek
    # ------------------------------------------------------------------

    def _seek_and_pause(self, frame_idx):
        self._stop_playback()
        self.btn_play.config(text='▶')
        self._seek(frame_idx)
        # Vide la queue d'événements : traite les KeyRelease/Press accumulés
        # pendant le seek pour éviter que la navigation continue après relâchement.
        # _updating empêche la récursion si un autre seek est déclenché par update().
        if not self._updating:
            self._updating = True
            self.root.update()
            self._updating = False

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
        iw, ih = img.size
        scale = min(w / iw, h / ih)
        img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
        imgtk = ImageTk.PhotoImage(img)
        self.canvas_video.imgtk = imgtk
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

    video_path, detections_by_class = read_csv(args.csv)

    if args.video:
        video_path = args.video

    if not video_path or not osp.isfile(video_path):
        print(f"[ERREUR] Vidéo introuvable : {video_path}")
        print("Utilisez --video pour spécifier le chemin manuellement.")
        return

    initial_classes = set(args.classes) if args.classes else None

    total_frames_det = sum(len(v) for v in detections_by_class.values())  # nb frames par classe (peut se chevaucher)
    print(f"[INFO] Vidéo      : {video_path}")
    print(f"[INFO] Classes    : {sorted(detections_by_class.keys())}")
    print(f"[INFO] Détections : {total_frames_det} entrée(s) au total")
    if initial_classes:
        print(f"[INFO] Visibles au démarrage : {sorted(initial_classes)}")

    root = tk.Tk()
    root.geometry('1280x760')
    VideoPlayer(root, video_path, detections_by_class, initial_classes)
    root.mainloop()


if __name__ == '__main__':
    main()
