"""Command-line installer. Prefer the Mod Launcher EXE for friends."""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from packager import install  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=pathlib.Path, help='Steam Happy Wheels folder (contains Happy Wheels.exe)')
    args = parser.parse_args()
    game = install(args.source)
    print('Patched Steam Happy Wheels:', game)


if __name__ == '__main__':
    main()
