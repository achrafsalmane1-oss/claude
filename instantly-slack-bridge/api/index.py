import os
import sys

# Make the app module (one directory up) importable on Vercel's Python runtime.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402  Vercel serves this WSGI `app`.
