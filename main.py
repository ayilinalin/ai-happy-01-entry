"""ai-happy-01 entry: write the chosen image to /output/entry.png.

Deterministic, stdlib only, no network. The entry image is the asset
entry.png shipped in this repo; this program copies it byte-for-byte
to /output/entry.png so both runs produce identical output.
"""

import os
import shutil
import sys


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "entry.png")
    out_dir = "/output"
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "entry.png")
    shutil.copyfile(src, dst)
    print("wrote", dst)


if __name__ == "__main__":
    sys.exit(main())
