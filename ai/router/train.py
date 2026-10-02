"""Train a 3-way LogisticRegression router on nomic-embed-text."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from langchain_ollama import OllamaEmbeddings
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.config import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, ROUTER_MODEL_PATH  # noqa: E402

TRAIN_PATH = ROOT / "eval" / "router_train.json"


def main() -> None:
    rows = json.loads(TRAIN_PATH.read_text(encoding="utf-8"))
    questions = [r["question"] for r in rows]
    labels = [r["route"] for r in rows]
    embed = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    print(f"Embedding {len(questions)} labeled questions with {OLLAMA_EMBED_MODEL}…")
    X = np.array(embed.embed_documents(questions))
    y = np.array(labels)
    clf = LogisticRegression(max_iter=400, class_weight="balanced")
    clf.fit(X, y)
    acc = float(clf.score(X, y))
    ROUTER_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump((clf, list(clf.classes_)), ROUTER_MODEL_PATH)
    print(f"Train accuracy (in-sample): {acc:.0%}")
    print(f"Wrote {ROUTER_MODEL_PATH}")
    print("Classes:", list(clf.classes_))


if __name__ == "__main__":
    main()
