# Met à jour les chemins vidéo dans les CSV de détections GCC-Net.
# Usage :
#   python update_csv_paths.py <dataset_root> <csv_root> [--dry-run]
#
# Exemples :
#   # Linux → Linux
#   python update_csv_paths.py /data/BORIS /results/Gcc-Net/BORIS --dry-run
#
#   # Linux → Windows (chemin cible Windows détecté automatiquement)
#   python update_csv_paths.py "D:\Videos\BORIS" /results/Gcc-Net/BORIS --dry-run
#
# Principe : le CSV à <csv_root>/MISSION/DATE/CAM/file.csv
#             correspond à la vidéo <dataset_root>/MISSION/DATE/CAM/file.MP4
# L'extension de la vidéo est préservée telle quelle (MP4, mp4, avi…).

import argparse
import re
import sys
from pathlib import Path, PureWindowsPath


def is_windows_path(path_str):
    """Détecte un chemin Windows : lettre de lecteur (C:\\, D:/, …)."""
    return bool(re.match(r'^[A-Za-z]:[/\\]', path_str))


def build_video_path(dataset_root_str, rel_video):
    """Construit le chemin vidéo final avec le bon séparateur (Linux ou Windows)."""
    if is_windows_path(dataset_root_str):
        # PureWindowsPath fonctionne sur Linux et génère des \ dans la sortie
        return PureWindowsPath(dataset_root_str) / str(rel_video)
    else:
        return Path(dataset_root_str) / rel_video


def update_csv(csv_path, csv_root, dataset_root_str, dry_run):
    lines = csv_path.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)

    new_lines = []
    changed   = False

    for line in lines:
        if not line.startswith('# video_path:'):
            new_lines.append(line)
            continue

        old_video = line.split(':', 1)[1].strip()
        old_ext   = Path(old_video).suffix   # conserve .MP4 / .mp4 / .avi …

        # Chemin relatif du CSV depuis csv_root, avec l'extension vidéo d'origine
        rel_video = csv_path.relative_to(csv_root).with_suffix(old_ext)
        new_video = build_video_path(dataset_root_str, rel_video)
        new_line  = f'# video_path: {new_video}\n'

        if new_line != line:
            changed = True
            print(f'  - {old_video}')
            print(f'  + {new_video}')

        new_lines.append(new_line)

    if changed and not dry_run:
        csv_path.write_text(''.join(new_lines), encoding='utf-8')

    return changed


def main():
    parser = argparse.ArgumentParser(
        description='Met à jour les chemins vidéo dans tous les CSV de détections')
    parser.add_argument('dataset',
                        help='Nouveau dossier racine du dataset '
                             '(ex: /data/BORIS  ou  D:\\Videos\\BORIS)')
    parser.add_argument('csv_dir',
                        help='Dossier racine des CSV (ex: /results/Gcc-Net/BORIS)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Affiche les changements sans modifier les fichiers')
    args = parser.parse_args()

    csv_root         = Path(args.csv_dir).resolve()
    dataset_root_str = args.dataset.rstrip('/\\')   # supprime le slash final éventuel
    windows_target   = is_windows_path(dataset_root_str)

    if not csv_root.is_dir():
        print(f'[ERREUR] Dossier CSV introuvable : {csv_root}')
        sys.exit(1)

    csv_files = sorted(csv_root.rglob('*.csv'))
    if not csv_files:
        print(f'[AVERTISSEMENT] Aucun CSV trouvé dans : {csv_root}')
        sys.exit(0)

    print(f'[INFO] {len(csv_files)} CSV trouvé(s) dans {csv_root}')
    print(f'[INFO] Nouveau dataset root : {dataset_root_str}')
    print(f'[INFO] Format cible : {"Windows (\\\\)" if windows_target else "Linux (/)"}')
    if args.dry_run:
        print('[INFO] Mode dry-run : aucun fichier ne sera modifié')
    print()

    n_changed = 0
    n_errors  = 0

    for csv_path in csv_files:
        rel = csv_path.relative_to(csv_root)
        try:
            changed = update_csv(csv_path, csv_root, dataset_root_str, args.dry_run)
        except Exception as exc:
            print(f'[ERREUR] {rel} : {exc}')
            n_errors += 1
            continue

        if changed:
            n_changed += 1
            tag = '(simulé)' if args.dry_run else 'modifié'
            print(f'  [{tag}] {rel}\n')

    verb = 'auraient été' if args.dry_run else 'ont été'
    print(f'[INFO] {n_changed}/{len(csv_files)} CSV {verb} modifié(s).'
          + (f' {n_errors} erreur(s).' if n_errors else ''))


if __name__ == '__main__':
    main()
