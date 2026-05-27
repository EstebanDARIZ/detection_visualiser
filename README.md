# GCC-Net Detection Viewer

Interactive video player for visualizing GCC-Net detections from CSV files.

---

## Setup

### Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows

Double-click `setup.bat`. It creates a `venv/` folder and installs all dependencies.

---

## Usage

### Linux

```bash
python view_detections.py path/to/detections.csv
```

With a custom video path (overrides the one stored in the CSV):

```bash
python view_detections.py path/to/detections.csv --video path/to/video.MP4
```

Show only specific classes on startup:

```bash
python view_detections.py path/to/detections.csv --classes 5 7
```

### Windows

**Drag-and-drop** the CSV file onto `launch.bat`.

Or from a terminal (Shift + right-click in the folder → *Open in Terminal*):

```bat
launch.bat "C:\path\to\detections.csv"
launch.bat "C:\path\to\detections.csv" --video "D:\Videos\BORIS\file.MP4"
launch.bat "C:\path\to\detections.csv" --classes 5 7
```

---

## CSV format

The CSV must contain a header comment with the video path:

```
# video_path: /path/to/video.MP4
frame_idx,timecode,class_id,class_name,score,x1,y1,x2,y2,inference_time_ms
0,00:00.000,5,Shark,0.82,100.0,200.0,300.0,400.0,12.3
...
```

---

## Interface

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` / `→` | Previous / Next frame |
| `a` / `e` | Previous / Next detection |
| `q` / `d` | Jump 10 detections backward / forward |
| `Page Up` / `Page Down` | Previous / Next detection |
| `Escape` | Quit |

### Class filter buttons

Each class present in the CSV has a colored toggle button at the bottom of the window. Click to show/hide detections for that class. The timeline marks and detection count update instantly.

| ID | Class | Color |
|----|-------|-------|
| 0 | Squid | violet |
| 1 | Sardine | yellow |
| 2 | Ray | green |
| 3 | Sunfish | orange |
| 4 | Pilot Fish | pink |
| 5 | Shark | red |
| 6 | JellyFish | mauve |
| 7 | Tuna | dark orange |
| 8 | Mackerel | lime green |

### Confidence threshold

Next to the class buttons, a slider lets you filter detections by minimum confidence score (0.00 – 1.00). You can also type a value directly in the field and press **Enter** to apply.

---

## Updating video paths across machines (`update_csv_paths.py`)

When transferring CSV files to a different machine (e.g. Linux → Windows), the video paths stored inside the CSVs need to be updated.

The script assumes that the CSV directory tree and the video dataset tree share the same relative structure:

```
csv_root/  MISSION/DATE/CAM/file.csv
dataset/   MISSION/DATE/CAM/file.MP4
```

### Preview changes without modifying files

```bash
python update_csv_paths.py /new/dataset/BORIS /path/to/csv/BORIS --dry-run
```

### Apply changes (Linux target)

```bash
python update_csv_paths.py /new/dataset/BORIS /path/to/csv/BORIS
```

### Apply changes (Windows target, run from Linux)

Provide a Windows-style path — the script detects it automatically and writes backslash-separated paths into the CSVs:

```bash
python update_csv_paths.py "D:\Videos\BORIS" /path/to/csv/BORIS
```

The resulting CSVs are ready to use on Windows: just transfer them and drag-drop onto `launch.bat`.
