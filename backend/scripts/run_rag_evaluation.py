#!/usr/bin/env python3
"""
Convenience launcher for the Apex Ops AI RAG Evaluation Framework.
Run locally with:
    python backend/scripts/run_rag_evaluation.py
    python backend/scripts/run_rag_evaluation.py --format markdown --output eval_report.md
"""
import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app.evaluation.runner import main

if __name__ == "__main__":
    main()
