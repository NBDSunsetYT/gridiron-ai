"""Explicit, local-only boundary for candidates not approved for deployment."""
import os

def local_only():
    if os.environ.get('VERCEL') or os.environ.get('RENDER'):raise RuntimeError('Unpromoted reconstruction research must execute locally, never in hosted request handlers')
