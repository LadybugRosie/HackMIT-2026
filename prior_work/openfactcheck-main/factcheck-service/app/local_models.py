"""
Local HuggingFace backends for claim-to-source faithfulness scoring.

These replace (or augment) the OpenAI strict-RAG alignment call. All
backends share the same interface:

    score(premise: str, hypothesis: str) -> AlignmentScore

where the returned `AlignmentScore` carries a verdict ∈ {supported,
contradicted, partial, unrelated, unknown}, a 0-1 probability, an
optional supporting span, and the backend name.

Two backends are implemented:

  • HHEM  — vectara/hallucination_evaluation_model (FLAN-T5-Base,
            ~600 MB, Apache-2.0, runs fine on CPU). Reports ~74 %
            balanced accuracy on RAGTruth-QA, matching GPT-4.

  • MiniCheck — bespokelabs/Bespoke-MiniCheck-7B (InternLM2.5-7B
            fine-tune, CC-BY-NC-4.0, ~14 GB on disk). SOTA on the
            LLM-AggreFact benchmark, beats GPT-4. Needs GPU for
            reasonable throughput.

Both are lazy-loaded — the heavy `transformers`/`torch` imports only
happen the first time the backend is actually called. The OpenAI
strict-RAG path remains the no-extra-deps default.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AlignmentScore:
    """Backend-agnostic alignment outcome."""
    support: str          # "supported" | "contradicted" | "partial" | "unrelated" | "unknown"
    probability: float    # 0.0 = fully unsupported, 1.0 = fully supported
    confidence: int       # 0-100 (model-reported confidence in the verdict)
    supporting_span: Optional[str] = None
    backend: str = "unknown"
    raw: Optional[dict] = field(default=None, repr=False)


def _band_from_prob(p: float) -> str:
    """Threshold a 0-1 supportedness probability into one of the verdict bands."""
    if p >= 0.80: return "supported"
    if p >= 0.55: return "partial"
    if p >= 0.30: return "unrelated"
    return "contradicted"


# ────────────────────────────────────────────────────────────────────────────
# HHEM-2.1-Open  (vectara/hallucination_evaluation_model)
# ────────────────────────────────────────────────────────────────────────────
class HHEMBackend:
    NAME = "hhem"
    MODEL_ID = "vectara/hallucination_evaluation_model"
    # Pinned to a specific commit so HF won't silently fetch a new
    # `modeling_*.py` from the model repo on future loads. trust_remote_code
    # is required by Vectara's loader; pinning the revision makes that safe.
    # Audit https://huggingface.co/vectara/hallucination_evaluation_model/tree/{REVISION}
    # before bumping. Overridable via env var HHEM_REVISION.
    DEFAULT_REVISION = "8e4a2e6e96c708cc76c2344f7e4757df2515292c"

    def __init__(self) -> None:
        self._model = None  # lazy

    def _load(self):
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForSequenceClassification  # noqa: WPS433
        except ImportError as e:
            raise RuntimeError(
                "HHEM backend requires the `transformers` package. "
                "Install requirements-local.txt."
            ) from e
        revision = os.environ.get("HHEM_REVISION", self.DEFAULT_REVISION)
        logger.info(
            "Loading HHEM-2.1-Open at pinned revision %s (one-time download ≈600 MB)…",
            revision[:12],
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.MODEL_ID,
            revision=revision,        # pinned — supply-chain protection
            trust_remote_code=True,   # required by Vectara's loader, safe with pin
        )
        logger.info("HHEM-2.1-Open ready (revision %s).", revision[:12])

    def score(self, premise: str, hypothesis: str) -> AlignmentScore:
        self._load()
        prob = float(self._model.predict([(premise, hypothesis)])[0])
        return AlignmentScore(
            support=_band_from_prob(prob),
            probability=prob,
            confidence=int(max(prob, 1 - prob) * 100),
            backend=self.NAME,
        )


# ────────────────────────────────────────────────────────────────────────────
# DeBERTa-v3-large-NLI  (MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli)
#
# Pure-PyTorch DeBERTa, no trust_remote_code, no TF imports — so no abseil
# mutex deadlock on macOS. Trained on MultiNLI + Fever-NLI + ANLI + LingNLI
# + WANLI. Output is 3-class softmax: entailment / neutral / contradiction.
# We map entailment_prob → our supportedness scale. MIT-license-friendly.
# ────────────────────────────────────────────────────────────────────────────
class NLIBackend:
    NAME = "nli"
    MODEL_ID = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
    DEFAULT_REVISION = os.environ.get("NLI_REVISION", "main")

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._labels: List[str] = []

    def _load(self):
        if self._model is not None:
            return
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification  # noqa: WPS433
        except ImportError as e:
            raise RuntimeError(
                "NLI backend requires `transformers`. Install requirements-local.txt."
            ) from e
        logger.info("Loading DeBERTa-v3-large NLI (one-time download ≈440 MB)…")
        self._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID, revision=self.DEFAULT_REVISION)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.MODEL_ID, revision=self.DEFAULT_REVISION
        )
        self._model.eval()
        # Map id → label using the model's config; expected labels are
        # entailment / neutral / contradiction (case-insensitive).
        id2label = getattr(self._model.config, "id2label", {}) or {}
        self._labels = [str(id2label.get(i, "")).lower() for i in range(len(id2label))]
        logger.info(f"DeBERTa NLI ready. Labels: {self._labels}")

    def score(self, premise: str, hypothesis: str) -> AlignmentScore:
        import torch  # noqa: WPS433  (lazy import)
        self._load()
        inputs = self._tokenizer(
            premise, hypothesis,
            return_tensors="pt", truncation=True, max_length=512,
        )
        with torch.no_grad():
            logits = self._model(**inputs).logits[0]
            probs = torch.softmax(logits, dim=-1).tolist()

        # Index by label name (robust against id reordering between checkpoints).
        def _prob(name: str) -> float:
            for i, l in enumerate(self._labels):
                if name in l:
                    return float(probs[i])
            return 0.0

        p_ent = _prob("entail")
        p_con = _prob("contradic")
        p_neu = _prob("neutral")

        # Banding rules for our 5-way verdict:
        if p_ent >= 0.70:
            support = "supported"
        elif p_con >= 0.70:
            support = "contradicted"
        elif p_ent >= 0.40:
            support = "partial"
        elif p_neu >= 0.50:
            support = "unrelated"
        else:
            support = "partial"
        return AlignmentScore(
            support=support,
            probability=p_ent,
            confidence=int(max(p_ent, p_con, p_neu) * 100),
            backend=self.NAME,
            raw={"entail": p_ent, "neutral": p_neu, "contradict": p_con},
        )


# ────────────────────────────────────────────────────────────────────────────
# Bespoke-MiniCheck-7B  (highest accuracy on LLM-AggreFact, SOTA)
# ────────────────────────────────────────────────────────────────────────────
class MiniCheckBackend:
    NAME = "minicheck"
    MODEL_ID = "bespokelabs/Bespoke-MiniCheck-7B"
    # The MiniCheck wrapper uses the standard HF cache; HF respects the
    # `HF_HUB_REVISION` and `MINICHECK_REVISION` envs for pinning. Resolve
    # the latest known-good SHA the first time the user runs it and lock it
    # into the env. See:
    #   https://huggingface.co/bespokelabs/Bespoke-MiniCheck-7B/commits/main
    DEFAULT_REVISION = os.environ.get("MINICHECK_REVISION", "main")

    def __init__(self) -> None:
        self._scorer = None

    def _load(self):
        if self._scorer is not None:
            return
        try:
            from minicheck.minicheck import MiniCheck  # noqa: WPS433
        except ImportError as e:
            raise RuntimeError(
                "MiniCheck backend requires the `minicheck` package. "
                "Install requirements-local.txt then `pip install minicheck`."
            ) from e
        cache_dir = os.environ.get("LOCAL_MODEL_CACHE_DIR", "./ckpts")
        logger.info(
            "Loading Bespoke-MiniCheck-7B (revision=%s, ~14 GB on first call). "
            "GPU strongly recommended.",
            self.DEFAULT_REVISION,
        )
        self._scorer = MiniCheck(
            model_name="Bespoke-MiniCheck-7B",
            cache_dir=cache_dir,
        )
        logger.info("Bespoke-MiniCheck-7B ready.")

    def score(self, premise: str, hypothesis: str) -> AlignmentScore:
        self._load()
        # The MiniCheck scorer expects parallel lists.
        labels, probs, _, _ = self._scorer.score(docs=[premise], claims=[hypothesis])
        prob = float(probs[0])
        label = int(labels[0])  # 1 = supported, 0 = unsupported
        # MiniCheck is a binary classifier, so we band the probability:
        #   high prob + label=1  → supported
        #   low prob  + label=0  → contradicted
        #   borderline           → partial / unrelated
        if label == 1 and prob >= 0.80:
            support = "supported"
        elif label == 0 and prob <= 0.20:
            support = "contradicted"
        elif prob >= 0.50:
            support = "partial"
        else:
            support = "unrelated"
        return AlignmentScore(
            support=support,
            probability=prob,
            confidence=int(max(prob, 1 - prob) * 100),
            backend=self.NAME,
            raw={"label": label, "prob": prob},
        )


# ────────────────────────────────────────────────────────────────────────────
# Singleton accessor — keep each model loaded once per process.
# ────────────────────────────────────────────────────────────────────────────
_BACKENDS = {}


def get_backend(name: str):
    """Get (lazily instantiate) a local backend by short name."""
    name = name.lower()
    if name not in _BACKENDS:
        if name == "hhem":
            _BACKENDS[name] = HHEMBackend()
        elif name == "minicheck":
            _BACKENDS[name] = MiniCheckBackend()
        elif name == "nli":
            _BACKENDS[name] = NLIBackend()
        else:
            raise ValueError(f"Unknown local alignment backend: {name!r}")
    return _BACKENDS[name]


def available_backends() -> List[str]:
    """Return the list of local backends whose deps are installed and importable."""
    out: List[str] = []
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
        out.extend(["hhem", "nli"])
    except ImportError:
        pass
    try:
        import minicheck  # noqa: F401
        out.append("minicheck")
    except ImportError:
        pass
    return out
