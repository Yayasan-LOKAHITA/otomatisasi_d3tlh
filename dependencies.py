# dependencies.py

import os
import sys

PLUGIN_DIR = os.path.dirname(__file__)
VENDOR_DIR = os.path.join(PLUGIN_DIR, "vendor")

if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)
