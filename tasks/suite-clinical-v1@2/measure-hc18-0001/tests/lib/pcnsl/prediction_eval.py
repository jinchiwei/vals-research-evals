"""Held-out mutation-prediction harness: fixed splits, comparable arms, aggregate scores.

Every arm (training prevalence, logistic regression, TabPFN, a direct LLM call, or
stored outputs from an agent run) gets the same patient-stratified folds and the
same feature columns for a gene. Arms receive training rows with labels and test
rows without labels; only the scorer in this module ever reads held-out labels.

Patient rows and per-patient probabilities stay in process memory on the data
host. The report holds aggregates only. Protocol: docs/research/prediction-protocol.md

Core logic is standard library only. numpy/scikit-learn/tabpfn are imported
lazily by the arms that need them and reported as unavailable when missing; no
arm is ever replaced by a substitute.
"""
import argparse
import hashlib
import importlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import random
import re
import shlex
import subprocess
import sys
from typing import NamedTuple

DEFAULT_SEED = 20261114
N_SPLITS = 5
MIN_CLASS_COUNT = 5
SIGNIFICANT_DIGITS = 6
SCHEMA = "pcnsl-prediction-eval/v1"
SCORE_DIRECTION = "fixed: higher probability = reported qualifying alteration; never flipped"
LABEL_DEFINITION = {"1": "qualifying alteration reported", "0": "no qualifying alteration reported"}
LABEL_CAVEAT = ("Label 0 means no qualifying alteration was reported for this gene. "
                "It does not establish that the gene is unaltered.")
_GENE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,31}")
_FEATURE = re.compile(r"[A-Za-z][A-Za-z0-9_. ()\-]{0,127}")
_TOKEN = re.compile(r"(train|test)-\d{3,}")


class ParseFailure(ValueError):
    """A model response that is not exactly the requested probability object."""


class ArmError(RuntimeError):
    """An arm failure whose message is a fixed code, safe to put in the report."""


class RequestTooLarge(ValueError):
    """A request over the configured size limit. Nothing is sent and nothing is truncated."""


class Fold(NamedTuple):
    """Everything an arm may see for one fold. There is deliberately no held-out label field."""
    gene: str
    fold: int
    n_folds: int
    feature_names: tuple
    train_ids: tuple
    train_X: tuple
    train_y: tuple
    test_ids: tuple
    test_X: tuple


def _digest(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


# ---------------------------------------------------------------- dataset checks

def canonical_matrix(X):
    """Numeric-or-None rows rounded to six significant digits, so every arm sees the same numbers."""
    rows = []
    width = None
    for row in X:
        out = []
        for value in row:
            if value is None:
                out.append(None)
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Features must be finite numbers or null")
            else:
                out.append(float(f"{float(value):.{SIGNIFICANT_DIGITS}g}"))
        if width is None:
            width = len(out)
        if len(out) != width:
            raise ValueError("Ragged feature matrix")
        rows.append(tuple(out))
    return tuple(rows)


def validate_dataset(dataset):
    """Check the load_dataset() contract. Returns the canonical feature matrix."""
    for key in ("case_ids", "feature_names", "X", "labels"):
        if key not in dataset:
            raise ValueError(f"Dataset is missing {key}")
    ids, names = list(dataset["case_ids"]), list(dataset["feature_names"])
    if not ids or len(set(ids)) != len(ids) or not all(isinstance(i, str) and i for i in ids):
        raise ValueError("case_ids must be unique non-empty strings")
    if not names or len(set(names)) != len(names) or not all(isinstance(n, str) for n in names):
        raise ValueError("feature_names must be unique strings")
    X = canonical_matrix(dataset["X"])
    if len(X) != len(ids) or any(len(row) != len(names) for row in X):
        raise ValueError("X must have one row per case and one column per feature")
    if not dataset["labels"]:
        raise ValueError("No labels")
    for gene, y in dataset["labels"].items():
        if not isinstance(gene, str) or not _GENE.fullmatch(gene):
            raise ValueError("Unexpected gene name")
        if len(y) != len(ids) or any(isinstance(v, bool) or v not in (0, 1) for v in y):
            raise ValueError("Labels must be one 0/1 value per case")
    for group, members in (dataset.get("feature_groups") or {}).items():
        if not set(members) <= set(names):
            raise ValueError(f"Feature group {group} names unknown features")
    groups = dataset.get("groups")
    if groups is not None and len(groups) != len(ids):
        raise ValueError("groups must have one patient key per case")
    return X


def select_features(dataset, feature_groups=None):
    """Column indices for the prespecified feature groups (None = every column), in dataset order."""
    names = list(dataset["feature_names"])
    if feature_groups is None:
        return list(range(len(names)))
    available = dataset.get("feature_groups") or {}
    wanted = set()
    for group in feature_groups:
        if group not in available:
            raise ValueError(f"Unknown feature group: {group}")
        wanted.update(available[group])
    columns = [j for j, name in enumerate(names) if name in wanted]
    if not columns:
        raise ValueError("Selected feature groups contain no features")
    return columns


def safe_feature_names(names):
    """Preserve vetted imaging metric descriptors, including region spaces and units.

    Paths, markup, control characters and long number strings remain disallowed.
    The release extractor separately enforces a fixed feature-name allowlist.
    """
    out = []
    for j, name in enumerate(names):
        ok = bool(_FEATURE.fullmatch(name)) and not re.search(r"\d{5,}", name)
        out.append(name if ok else f"feature_{j:03d}")
    if len(set(out)) != len(out):
        raise ValueError("Feature names collide after sanitizing")
    return tuple(out)


def eligible_genes(labels, min_class_count=MIN_CLASS_COUNT):
    """Genes with enough patients in both classes. Uses label counts only, never scores."""
    eligible, excluded = [], {}
    for gene in sorted(labels):
        positive = sum(labels[gene]); negative = len(labels[gene]) - positive
        if min(positive, negative) >= min_class_count:
            eligible.append(gene)
        else:
            excluded[gene] = {"positive": positive, "no_qualifying_report": negative,
                              "reason": f"fewer than {min_class_count} patients in one class"}
    return eligible, excluded


# ---------------------------------------------------------------- splits

def make_splits(case_ids, y, gene, seed=DEFAULT_SEED, n_splits=N_SPLITS, groups=None,
                min_class_count=MIN_CLASS_COUNT):
    """Patient-stratified folds that depend only on (seed, gene, patient key, label).

    Patients are ordered within each class by a SHA-256 of the seed, gene and
    patient key, then dealt round-robin. The result does not depend on row order,
    Python version or any library, so every host and every arm gets the same folds.
    """
    case_ids = list(case_ids); y = list(y)
    if len(case_ids) != len(y) or len(set(case_ids)) != len(case_ids):
        raise ValueError("Need one label per unique case")
    if any(isinstance(v, bool) or v not in (0, 1) for v in y):
        raise ValueError("Labels must be 0 or 1")
    units = list(groups) if groups is not None else case_ids
    if len(units) != len(case_ids):
        raise ValueError("Need one patient key per case")
    unit_label = {}
    for unit, label in zip(units, y):
        if unit_label.setdefault(unit, label) != label:
            raise ValueError("A patient has conflicting labels across rows")
    by_class = {c: sorted((u for u, v in unit_label.items() if v == c),
                          key=lambda u: _digest(seed, gene, u)) for c in (1, 0)}
    smallest = min(len(by_class[0]), len(by_class[1]))
    if smallest < max(min_class_count, n_splits):
        raise ValueError("Too few patients in one class for these folds")
    assignment = {}
    for j, unit in enumerate(by_class[1]):
        assignment[unit] = j % n_splits
    offset = len(by_class[1]) % n_splits      # keeps total fold sizes within one of each other
    for j, unit in enumerate(by_class[0]):
        assignment[unit] = (offset + j) % n_splits
    folds = []
    for k in range(n_splits):
        test = [i for i, u in enumerate(units) if assignment[u] == k]
        train = [i for i, u in enumerate(units) if assignment[u] != k]
        if {y[i] for i in test} != {0, 1} or {y[i] for i in train} != {0, 1}:
            raise ValueError("A fold is missing a class")
        folds.append({"train": train, "test": test})
    return folds


def split_fingerprint(case_ids, folds):
    """Order-independent hash of which case is tested in which fold."""
    pairs = sorted((case_ids[i], k) for k, fold in enumerate(folds) for i in fold["test"])
    return _digest(json.dumps(pairs))


def build_fold(case_ids, feature_names, X, y, split, gene, fold, seed=DEFAULT_SEED,
               n_folds=N_SPLITS, return_key=False):
    """Arm inputs for one fold. Reads labels at training indices only.

    Cases get fold-local opaque tokens in a hash order that is independent of the
    label. With return_key=True also returns the row index behind each test token,
    which only the scorer should hold.
    """
    def order(role, indices):
        return sorted(indices, key=lambda i: _digest(seed, gene, fold, role, case_ids[i]))
    train, test = order("train", split["train"]), order("test", split["test"])
    view = Fold(gene=gene, fold=fold, n_folds=n_folds, feature_names=safe_feature_names(feature_names),
                train_ids=tuple(f"train-{n + 1:03d}" for n in range(len(train))),
                train_X=tuple(tuple(X[i]) for i in train),
                train_y=tuple(int(y[i]) for i in train),
                test_ids=tuple(f"test-{n + 1:03d}" for n in range(len(test))),
                test_X=tuple(tuple(X[i]) for i in test))
    return (view, test) if return_key else view


# ---------------------------------------------------------------- train-only preprocessing

def fit_preprocessor(train_rows):
    """Median imputation and standardization fitted on training rows only."""
    width = len(train_rows[0])
    median, mean, scale, all_missing = [], [], [], []
    for j in range(width):
        present = sorted(row[j] for row in train_rows if row[j] is not None)
        if not present:
            all_missing.append(j); median.append(0.0); mean.append(0.0); scale.append(1.0)
            continue
        mid = len(present) // 2
        m = present[mid] if len(present) % 2 else (present[mid - 1] + present[mid]) / 2
        filled = [m if row[j] is None else row[j] for row in train_rows]
        mu = sum(filled) / len(filled)
        sd = math.sqrt(sum((v - mu) ** 2 for v in filled) / len(filled))
        median.append(m); mean.append(mu); scale.append(sd if sd > 0 else 1.0)
    return {"median": median, "mean": mean, "scale": scale, "all_missing": all_missing}


def apply_preprocessor(prep, rows):
    """Apply training-fold parameters. Columns with no training values become 0."""
    dead = set(prep["all_missing"])
    return [[0.0 if j in dead else ((prep["median"][j] if v is None else v) - prep["mean"][j]) / prep["scale"][j]
             for j, v in enumerate(row)] for row in rows]


# ---------------------------------------------------------------- direct-LLM interface

def build_llm_payload(fold):
    """The sanitized request for one fold: training rows with labels, test rows without."""
    return {
        "task": ("Estimate, for each test case, the probability that a qualifying alteration in the target gene "
                 "was reported. Cases are adult patients with primary CNS lymphoma; features come from MRI and "
                 "released clinical variables. Use only the rows provided."),
        "target_gene": fold.gene,
        "label_definition": dict(LABEL_DEFINITION),
        "label_caveat": LABEL_CAVEAT,
        "feature_names": list(fold.feature_names),
        "missing_value": "null means the feature was not measured",
        "train": [{"case": c, "features": list(x), "label": int(t)}
                  for c, x, t in zip(fold.train_ids, fold.train_X, fold.train_y)],
        "test": [{"case": c, "features": list(x)} for c, x in zip(fold.test_ids, fold.test_X)],
        "response_format": ('Reply with one JSON object and nothing else: {"predictions": [{"case": "test-001", '
                            '"probability": 0.5}, ...]}. Include every test case exactly once. "probability" is a '
                            "number from 0 to 1 for label 1."),
    }


_PAYLOAD_KEYS = {"task", "target_gene", "label_definition", "label_caveat", "feature_names",
                 "missing_value", "train", "test", "response_format"}


def assert_payload_sanitized(payload, forbidden=()):
    """Refuse a request that carries anything beyond tokens, numbers and training labels."""
    if set(payload) != _PAYLOAD_KEYS:
        raise ValueError("Unexpected request fields")
    width = len(payload["feature_names"])
    for role, keys in (("train", {"case", "features", "label"}), ("test", {"case", "features"})):
        for row in payload[role]:
            if set(row) != keys:
                raise ValueError(f"Unexpected fields in a {role} row")
            match = _TOKEN.fullmatch(row["case"]) if isinstance(row["case"], str) else None
            if not match or match.group(1) != role:
                raise ValueError("Case tokens must be fold-local")
            if len(row["features"]) != width or any(
                    v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v))
                    for v in row["features"]):
                raise ValueError("Features must be finite numbers or null")
            if role == "train" and (isinstance(row["label"], bool) or row["label"] not in (0, 1)):
                raise ValueError("Training labels must be 0 or 1")
    if list(safe_feature_names(payload["feature_names"])) != list(payload["feature_names"]):
        raise ValueError("Feature names are not sanitized")
    text = json.dumps(payload, allow_nan=False)
    if any(isinstance(token, str) and token and token in text for token in forbidden):
        raise ValueError("Request contains a cohort identifier")
    return True


def _reject_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ParseFailure("duplicate_key")
    return dict(pairs)


def _reject_constant(_):
    raise ParseFailure("non_finite_number")


def parse_probabilities(text, expected_ids):
    """Strictly parse {"predictions": [{"case": ..., "probability": ...}, ...]}.

    Accepts the bare object or the object inside one code fence. Nothing is
    repaired, clipped, rescaled or inferred; any deviation raises ParseFailure
    with a fixed reason code (never the response text).
    """
    if not isinstance(text, str):
        raise ParseFailure("not_text")
    body = text.strip()
    if body.startswith("```"):
        match = re.fullmatch(r"```(?:json)?[ \t]*\n(.*)\n```", body, flags=re.DOTALL)
        if not match or "```" in match.group(1):
            raise ParseFailure("malformed_code_fence")
        body = match.group(1).strip()
    if not body.startswith("{"):
        raise ParseFailure("not_a_json_object")
    try:
        data = json.loads(body, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant)
    except ParseFailure:
        raise
    except (ValueError, RecursionError):
        raise ParseFailure("invalid_json") from None
    if not isinstance(data, dict) or set(data) != {"predictions"} or not isinstance(data["predictions"], list):
        raise ParseFailure("wrong_top_level_shape")
    expected = list(expected_ids)
    found = {}
    for item in data["predictions"]:
        if not isinstance(item, dict) or set(item) != {"case", "probability"}:
            raise ParseFailure("wrong_item_shape")
        case, p = item["case"], item["probability"]
        if not isinstance(case, str) or case not in set(expected):
            raise ParseFailure("unknown_case")
        if case in found:
            raise ParseFailure("duplicate_case")
        if isinstance(p, bool) or not isinstance(p, (int, float)):
            raise ParseFailure("probability_not_a_number")
        if not math.isfinite(p) or p < 0 or p > 1:
            raise ParseFailure("probability_out_of_range")
        found[case] = float(p)
    if len(found) != len(expected):
        raise ParseFailure("missing_case")
    return [found[case] for case in expected]


# ---------------------------------------------------------------- metrics

def _check(y, p):
    if len(y) != len(p) or not y:
        raise ValueError("Need one score per label")


def auroc(y, p):
    """Area under the ROC curve with tied scores counted as half. Direction is never flipped."""
    _check(y, p)
    n_pos = sum(y); n_neg = len(y) - n_pos
    if not n_pos or not n_neg:
        raise ValueError("AUROC needs both classes")
    order = sorted(range(len(p)), key=lambda i: p[i])
    rank_sum = 0.0; i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and p[order[j + 1]] == p[order[i]]:
            j += 1
        midrank = (i + j) / 2 + 1
        rank_sum += midrank * sum(y[order[k]] for k in range(i, j + 1))
        i = j + 1
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def average_precision(y, p):
    """Step-wise average precision over distinct score thresholds (scikit-learn's definition)."""
    _check(y, p)
    n_pos = sum(y)
    if not n_pos:
        raise ValueError("Average precision needs a positive case")
    order = sorted(range(len(p)), key=lambda i: -p[i])
    total = 0.0; tp = 0; seen = 0; previous_recall = 0.0; i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and p[order[j + 1]] == p[order[i]]:
            j += 1
        tp += sum(y[order[k]] for k in range(i, j + 1)); seen = j + 1
        recall = tp / n_pos
        total += (recall - previous_recall) * (tp / seen)
        previous_recall = recall; i = j + 1
    return total


def brier(y, p):
    _check(y, p)
    return sum((pi - yi) ** 2 for yi, pi in zip(y, p)) / len(y)


METRICS = {"auroc": auroc, "average_precision": average_precision, "brier": brier}


def _percentile(sorted_values, q):
    position = q * (len(sorted_values) - 1)
    low = int(math.floor(position)); high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


# ---------------------------------------------------------------- arms

class TrainingPrevalenceArm:
    """Every test case gets the training-fold positive fraction."""
    name = "training_prevalence"
    safe_error_messages = True

    def availability(self):
        return {"available": True}

    def predict_fold(self, fold):
        return [sum(fold.train_y) / len(fold.train_y)] * len(fold.test_X)


class LogisticRegressionArm:
    """L2 logistic regression, C=1, no tuning; imputation and scaling fitted on the training fold."""
    name = "logistic_regression"
    safe_error_messages = True
    settings = {"C": 1.0, "penalty": "l2", "solver": "lbfgs", "max_iter": 5000, "hyperparameter_search": False}

    def availability(self):
        missing = [m for m in ("numpy", "sklearn") if importlib.util.find_spec(m) is None]
        if missing:
            return {"available": False, "reason": f"{', '.join(missing)} not installed; logistic regression was not run"}
        return {"available": True}

    def describe(self):
        import numpy, sklearn
        return {"settings": dict(self.settings),
                "versions": {"numpy": numpy.__version__, "scikit_learn": sklearn.__version__}}

    def predict_fold(self, fold):
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        prep = fit_preprocessor(fold.train_X)
        model = LogisticRegression(C=self.settings["C"], solver=self.settings["solver"],
                                   max_iter=self.settings["max_iter"])
        model.fit(np.asarray(apply_preprocessor(prep, fold.train_X), dtype=float), np.asarray(fold.train_y))
        column = list(model.classes_).index(1)
        proba = model.predict_proba(np.asarray(apply_preprocessor(prep, fold.test_X), dtype=float))
        return [float(v) for v in proba[:, column]]


class TabPFNArm:
    """The real tabpfn.TabPFNClassifier with package defaults and a named local checkpoint.

    Offline by default: it needs an explicit checkpoint file (model_path) and sets
    the Hugging Face offline switches before tabpfn is imported, so nothing is
    downloaded. If tabpfn, the checkpoint or a needed constructor parameter is
    missing, the arm is reported unavailable. No other model is ever substituted.
    """
    name = "tabpfn"
    safe_error_messages = False      # hub/auth errors can carry URLs or tokens; only fixed codes are recorded

    def __init__(self, seed=DEFAULT_SEED, device=None, model_path=None, offline=True,
                 importer=importlib.import_module):
        self.seed = seed; self.device = device; self.offline = bool(offline)
        self.model_path = Path(model_path) if model_path is not None else None
        self._importer = importer; self._checkpoint_sha256 = None

    def _unavailable(self, why):
        return {"available": False, "reason": f"{why}; TabPFN was not run and no substitute model was used"}

    def availability(self):
        if self.offline:
            os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ.setdefault("TABPFN_DISABLE_TELEMETRY", "1")
        try:
            tabpfn = self._importer("tabpfn"); self._importer("numpy")
        except Exception as exc:
            return self._unavailable(f"tabpfn could not be imported ({type(exc).__name__})")
        parameters = inspect.signature(tabpfn.TabPFNClassifier.__init__).parameters
        if self.model_path is None and self.offline:
            return self._unavailable("offline mode needs an explicit local tabpfn checkpoint (model_path) and none was given")
        if self.model_path is not None:
            if "model_path" not in parameters:
                return self._unavailable("the installed tabpfn does not accept a model_path")
            if not self.model_path.is_file():
                return self._unavailable("the configured tabpfn checkpoint file does not exist")
            digest = hashlib.sha256()
            with self.model_path.open("rb") as stream:
                for block in iter(lambda: stream.read(1 << 20), b""):
                    digest.update(block)
            self._checkpoint_sha256 = digest.hexdigest()
        if self.device and "device" not in parameters:
            return self._unavailable("the installed tabpfn does not accept a device")
        if "random_state" not in parameters and "seed" not in parameters:
            return self._unavailable("the installed tabpfn does not accept a random seed")
        return {"available": True}

    def _kwargs(self, cls):
        parameters = inspect.signature(cls.__init__).parameters
        kwargs = {"random_state" if "random_state" in parameters else "seed": self.seed}
        if self.device:
            kwargs["device"] = self.device
        if self.model_path is not None:
            kwargs["model_path"] = str(self.model_path)
        return kwargs

    def describe(self):
        tabpfn = self._importer("tabpfn")
        try:
            import importlib.metadata
            version = importlib.metadata.version("tabpfn")
        except Exception:
            version = getattr(tabpfn, "__version__", "unknown")
        kwargs = self._kwargs(tabpfn.TabPFNClassifier)
        kwargs.pop("model_path", None)
        return {"settings": {"model": "tabpfn.TabPFNClassifier", "other_parameters": "package defaults", **kwargs,
                             "checkpoint_file": self.model_path.name if self.model_path else "package default (download allowed)",
                             "checkpoint_sha256": self._checkpoint_sha256, "offline": self.offline,
                             "missing_values": "passed as NaN", "hyperparameter_search": False},
                "versions": {"tabpfn": version}}

    def predict_fold(self, fold):
        tabpfn = self._importer("tabpfn"); np = self._importer("numpy")
        as_array = lambda rows: np.asarray([[float("nan") if v is None else v for v in row] for row in rows], dtype=float)
        stage = "construct"
        try:
            model = tabpfn.TabPFNClassifier(**self._kwargs(tabpfn.TabPFNClassifier))
            stage = "fit"
            model.fit(as_array(fold.train_X), np.asarray(fold.train_y))
            stage = "predict"
            column = [int(c) for c in model.classes_].index(1)
            return [float(v) for v in model.predict_proba(as_array(fold.test_X))[:, column]]
        except Exception as exc:
            raise ArmError(f"tabpfn_{stage}_failed:{type(exc).__name__}") from None


class DirectLLMArm:
    """One request per fold to a caller-supplied client: client(request_json_text) -> response text.

    The harness never opens a network connection itself. Responses go through the
    strict parser; a response that fails is recorded as a failure, not repaired.
    """
    name = "direct_llm"
    safe_error_messages = False      # client errors may echo the request, so only the type is recorded

    def __init__(self, client=None, model_label="unspecified", max_attempts=1, name=None,
                 only_folds=None, max_request_chars=None):
        self.client = client; self.model_label = model_label; self.max_attempts = int(max_attempts)
        self.only_folds = sorted(set(only_folds)) if only_folds is not None else None
        self.max_request_chars = max_request_chars
        if name:
            self.name = name

    def availability(self):
        if self.client is None:
            return {"available": False,
                    "reason": "no model client configured; nothing was sent and no scores were generated"}
        return {"available": True}

    def describe(self):
        return {"model_label": self.model_label, "max_attempts_per_fold": self.max_attempts,
                "max_request_chars": self.max_request_chars,
                "request": "one JSON request per fold: labelled training rows and unlabelled test rows"}

    def predict_fold(self, fold):
        payload = build_llm_payload(fold)
        assert_payload_sanitized(payload)
        request = json.dumps(payload, allow_nan=False)
        if self.max_request_chars is not None and len(request) > self.max_request_chars:
            raise RequestTooLarge("request_over_size_limit")
        for attempt in range(self.max_attempts):
            try:
                return parse_probabilities(self.client(request), fold.test_ids)
            except ParseFailure:
                if attempt == self.max_attempts - 1:
                    raise


class ReplayArm(DirectLLMArm):
    """Scores stored responses (for example files written by an agent run) with the same parser and folds.

    responses maps (gene, fold_index) to the response text for that fold's request.
    """
    def __init__(self, name, responses, model_label="stored responses"):
        def lookup(request, _responses=responses):
            payload = json.loads(request)
            return _responses[(payload["target_gene"], self._current_fold)]
        super().__init__(client=lookup, model_label=model_label, max_attempts=1, name=name)

    def predict_fold(self, fold):
        self._current_fold = fold.fold
        return super().predict_fold(fold)


ARMS = {"training_prevalence": TrainingPrevalenceArm, "logistic_regression": LogisticRegressionArm,
        "tabpfn": TabPFNArm}


# ---------------------------------------------------------------- evaluation

def _prepare(dataset, seed, n_splits, min_class_count, feature_groups, genes):
    X_all = validate_dataset(dataset)
    columns = select_features(dataset, feature_groups)
    names = [dataset["feature_names"][j] for j in columns]
    X = tuple(tuple(row[j] for j in columns) for row in X_all)
    eligible, excluded = eligible_genes(dataset["labels"], min_class_count)
    if genes is not None:
        unknown = sorted(set(genes) - set(dataset["labels"]))
        if unknown:
            raise ValueError(f"Unknown genes requested: {unknown}")
        for gene in eligible:
            if gene not in genes:
                excluded[gene] = {"positive": sum(dataset["labels"][gene]),
                                  "no_qualifying_report": len(X) - sum(dataset["labels"][gene]),
                                  "reason": "not in the prespecified gene list for this run"}
        eligible = [g for g in eligible if g in genes]
    return X, names, eligible, excluded


def iter_folds(dataset, seed=DEFAULT_SEED, n_splits=N_SPLITS, min_class_count=MIN_CLASS_COUNT,
               feature_groups=None, genes=None):
    """Yield (gene, fold_index, Fold) for exactly the folds run_evaluation uses.

    For building agent tasks from the same splits: build_llm_payload(fold) is the
    public input and ReplayArm scores what comes back. Contains patient rows, so
    whatever consumes this must stay on the data host or an approved endpoint.
    """
    X, names, eligible, _ = _prepare(dataset, seed, n_splits, min_class_count, feature_groups, genes)
    ids = list(dataset["case_ids"])
    for gene in eligible:
        y = dataset["labels"][gene]
        for k, split in enumerate(make_splits(ids, y, gene, seed, n_splits, dataset.get("groups"), min_class_count)):
            yield gene, k, build_fold(ids, names, X, y, split, gene, k, seed, n_splits)


def _validated(probabilities, expected):
    values = list(probabilities) if isinstance(probabilities, (list, tuple)) else None
    if values is None or len(values) != expected:
        raise ValueError("wrong number of probabilities")
    for v in values:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 1:
            raise ValueError("probability outside 0-1")
    return [float(v) for v in values]


def run_evaluation(dataset, arms, seed=DEFAULT_SEED, n_splits=N_SPLITS, min_class_count=MIN_CLASS_COUNT,
                   feature_groups=None, genes=None, bootstrap=2000):
    """Run every arm on identical folds and return an aggregate-only report.

    Held-out labels are read only here, after an arm has returned its
    probabilities. Per-patient probabilities are discarded when this returns.
    """
    names_seen = [arm.name for arm in arms]
    if len(set(names_seen)) != len(names_seen):
        raise ValueError("Arm names must be unique")
    X, names, eligible, excluded = _prepare(dataset, seed, n_splits, min_class_count, feature_groups, genes)
    ids = list(dataset["case_ids"]); groups = dataset.get("groups")
    feature_print = _digest(json.dumps(names))
    renamed = sum(1 for a, b in zip(names, safe_feature_names(names)) if a != b)
    availability = {arm.name: arm.availability() for arm in arms}
    report = {"schema": SCHEMA, "genes": {}, "excluded_genes": excluded}
    for gene in eligible:
        y = list(dataset["labels"][gene])
        folds = make_splits(ids, y, gene, seed, n_splits, groups, min_class_count)
        split_print = split_fingerprint(ids, folds)
        gene_result = {"patients": len(set(groups)) if groups is not None else len(ids), "rows": len(ids),
                       "positive": sum(y), "no_qualifying_report": len(y) - sum(y),
                       "fold_sizes": [{"train": len(f["train"]), "test": len(f["test"]),
                                       "test_positive": sum(y[i] for i in f["test"])} for f in folds],
                       "arms": {}}
        out_of_fold = {}
        for arm in arms:
            result = {"status": "complete", "folds_completed": 0, "pooled_oof": None,
                      "split_fingerprint": split_print, "feature_fingerprint": feature_print}
            if hasattr(arm, "describe") and availability[arm.name]["available"]:
                result.update(arm.describe())
            gene_result["arms"][arm.name] = result
            if not availability[arm.name]["available"]:
                result.update(status="unavailable", reason=availability[arm.name]["reason"])
                continue
            scores = [None] * len(ids); failures = []; per_fold = []
            only = getattr(arm, "only_folds", None)
            if only is not None and (not only or not set(only) <= set(range(n_splits))):
                raise ValueError("only_folds must name existing folds")
            for k, split in enumerate(folds):
                if only is not None and k not in only:
                    continue
                view, key = build_fold(ids, names, X, y, split, gene, k, seed, n_splits, return_key=True)
                try:
                    probabilities = _validated(arm.predict_fold(view), len(key))
                except ParseFailure as exc:
                    failures.append({"fold": k, "kind": "parse_failure", "reason": str(exc)}); continue
                except RequestTooLarge:
                    failures.append({"fold": k, "kind": "request_too_large"}); continue
                except Exception as exc:  # an arm that breaks is reported, never patched
                    failure = {"fold": k, "kind": "error", "error_type": type(exc).__name__}
                    if isinstance(exc, ArmError) or getattr(arm, "safe_error_messages", False):
                        failure["message"] = str(exc)[:300]
                    failures.append(failure); continue
                for index, probability in zip(key, probabilities):   # held-out labels are first used below
                    scores[index] = probability
                truth = [y[i] for i in key]
                per_fold.append({"fold": k, "test_rows": len(key), "test_positive": sum(truth),
                                 **{name: metric(truth, probabilities) for name, metric in METRICS.items()}})
                result["folds_completed"] += 1
            result["per_fold"] = per_fold
            if failures:
                kinds = {f["kind"] for f in failures}
                result.update(status=kinds.pop() if len(kinds) == 1 else "error", failures=failures)
                continue
            if only is not None and len(only) < n_splits:
                result.update(status="partial", folds_requested=list(only),
                              note="a prespecified subset of folds was run; compare per_fold entries, not pooled scores")
                continue
            out_of_fold[arm.name] = scores
            result["pooled_oof"] = {name: metric(y, scores) for name, metric in METRICS.items()}
            fold_auroc = [f["auroc"] for f in per_fold]
            result["fold_auroc"] = {"mean": sum(fold_auroc) / len(fold_auroc), "min": min(fold_auroc), "max": max(fold_auroc)}
        gene_result.update(_uncertainty(y, out_of_fold, gene_result["arms"], groups or ids, seed, gene, bootstrap))
        report["genes"][gene] = gene_result
    report["summary"] = _summary(report["genes"], names_seen)
    report["design"] = {
        "seed": seed, "folds": n_splits, "min_class_count": min_class_count,
        "split_method": "patient-stratified; SHA-256 ordering of (seed, gene, patient key) within class, dealt round-robin",
        "splits_shared_by_all_arms": True, "feature_groups": list(feature_groups) if feature_groups else ["<all columns>"],
        "feature_count": len(names), "feature_fingerprint": feature_print, "feature_names_replaced_by_placeholders": renamed,
        "feature_rounding_significant_digits": SIGNIFICANT_DIGITS, "arms": names_seen,
        "gene_eligibility": f"at least {min_class_count} patients in each class, decided from label counts before any model is run",
        "endpoint": LABEL_CAVEAT, "score_direction": SCORE_DIRECTION,
        "preprocessing": "imputation and scaling are fitted inside each training fold; test rows never inform them",
        "held_out_labels": "never passed to an arm; read only by the scorer after probabilities are returned",
        "selection": "no hyperparameter search, no model or gene selection on held-out results",
        "bootstrap": {"resamples": bootstrap, "unit": "patient", "interval": "percentile 2.5-97.5",
                      "note": "conditional on the fitted folds; not a confidence interval for a new cohort"},
        "patient_level_outputs": False,
    }
    if isinstance(dataset.get("metadata"), dict):
        report["dataset_metadata"] = dataset["metadata"]
    json.dumps(report, allow_nan=False)
    return report


def _uncertainty(y, out_of_fold, arm_results, units, seed, gene, bootstrap):
    """Patient-level bootstrap of pooled out-of-fold metrics, with the same resamples for every arm."""
    names = list(out_of_fold)
    differences = {}
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            differences[f"{second}_minus_{first}"] = {
                "difference": arm_results[second]["pooled_oof"]["auroc"] - arm_results[first]["pooled_oof"]["auroc"]}
    if not bootstrap or not names:
        return {"paired_auroc_differences": differences}
    rows_of = {}
    for index, unit in enumerate(units):
        rows_of.setdefault(unit, []).append(index)
    keys = sorted(rows_of, key=str)
    rng = random.Random(int(_digest(seed, gene, "bootstrap")[:16], 16))
    draws = {name: {metric: [] for metric in METRICS} for name in names}
    delta = {key: [] for key in differences}
    skipped = 0
    for _ in range(bootstrap):
        sample = [i for unit in rng.choices(keys, k=len(keys)) for i in rows_of[unit]]
        ys = [y[i] for i in sample]
        if len(set(ys)) < 2:
            skipped += 1; continue
        current = {}
        for name in names:
            ps = [out_of_fold[name][i] for i in sample]
            for metric, function in METRICS.items():
                value = function(ys, ps); draws[name][metric].append(value)
                if metric == "auroc":
                    current[name] = value
        for i, first in enumerate(names):
            for second in names[i + 1:]:
                delta[f"{second}_minus_{first}"].append(current[second] - current[first])
    interval = lambda values: [_percentile(sorted(values), 0.025), _percentile(sorted(values), 0.975)] if values else None
    for name in names:
        arm_results[name]["bootstrap_95"] = {metric: interval(values) for metric, values in draws[name].items()}
    for key in differences:
        differences[key]["bootstrap_95"] = interval(delta[key])
    return {"paired_auroc_differences": differences, "bootstrap_resamples_skipped_one_class": skipped}


def _summary(genes, arm_names):
    """Unweighted mean across genes for arms that completed every gene's folds."""
    summary = {}
    for name in arm_names:
        done = [g["arms"][name]["pooled_oof"] for g in genes.values() if g["arms"][name]["pooled_oof"]]
        statuses = sorted({g["arms"][name]["status"] for g in genes.values()})
        entry = {"genes_scored": len(done), "genes_total": len(genes), "statuses": statuses}
        if done:
            entry["mean_across_genes"] = {metric: sum(d[metric] for d in done) / len(done) for metric in METRICS}
        summary[name] = entry
    return summary


# ---------------------------------------------------------------- integration API

def _feature_groups_arg(dataset, feature_group):
    """'all' means the dataset's own 'all' group when it has one, otherwise every column."""
    if feature_group is None:
        return None
    groups = [feature_group] if isinstance(feature_group, str) else list(feature_group)
    if groups == ["all"] and "all" not in (dataset.get("feature_groups") or {}):
        return None
    return groups


def make_folds(dataset, gene, n_splits=N_SPLITS, seed=DEFAULT_SEED, min_class_count=MIN_CLASS_COUNT):
    """The folds every arm uses for this gene: [{'train': [row, ...], 'test': [row, ...]}, ...]."""
    validate_dataset(dataset)
    return make_splits(dataset["case_ids"], dataset["labels"][gene], gene, seed, n_splits,
                       dataset.get("groups"), min_class_count)


def build_public_payload(dataset, gene, train, test, feature_group="all", fold=0, seed=DEFAULT_SEED,
                         n_splits=N_SPLITS):
    """Request for one fold plus the evaluator's key.

    Returns (payload, test_rows). payload is what a model or agent may see.
    test_rows[i] is the dataset row behind payload['test'][i]; keep it with the
    trusted evaluator. Labels are read at the training rows only.
    """
    X_all = validate_dataset(dataset)
    if set(train) & set(test):
        raise ValueError("Train and test rows overlap")
    columns = select_features(dataset, _feature_groups_arg(dataset, feature_group))
    names = [dataset["feature_names"][j] for j in columns]
    X = tuple(tuple(row[j] for j in columns) for row in X_all)
    view, key = build_fold(dataset["case_ids"], names, X, dataset["labels"][gene],
                           {"train": list(train), "test": list(test)}, gene, fold, seed, n_splits, return_key=True)
    payload = build_llm_payload(view)
    assert_payload_sanitized(payload, dataset["case_ids"])
    return payload, key


def parse_predictions(response, expected_case_ids):
    """Strict parser for a model or agent response; see parse_probabilities."""
    return parse_probabilities(response, expected_case_ids)


def evaluate_probabilities(y, p):
    """AUROC, average precision and Brier score for probabilities of label 1. Nothing is flipped or clipped."""
    p = _validated(p, len(y))
    if any(isinstance(v, bool) or v not in (0, 1) for v in y):
        raise ValueError("Labels must be 0 or 1")
    return {name: metric(list(y), p) for name, metric in METRICS.items()}


def run_baselines(dataset, genes=None, feature_group="all", arms=("training_prevalence", "logistic_regression", "tabpfn"),
                  seed=DEFAULT_SEED, n_splits=N_SPLITS, min_class_count=MIN_CLASS_COUNT, bootstrap=2000, extra_arms=()):
    """Tabular baselines (plus any extra arms, e.g. DirectLLMArm) on the shared folds. Aggregate report.

    arms takes names or arm objects, e.g. TabPFNArm(model_path=...). A bare
    "tabpfn" is offline with no checkpoint, so it is reported unavailable.
    """
    built = [ARMS[arm]() if isinstance(arm, str) else arm for arm in arms]
    return run_evaluation(dataset, built + list(extra_arms), seed, n_splits, min_class_count,
                          _feature_groups_arg(dataset, feature_group), genes, bootstrap)


def payload_preflight(dataset, genes=None, feature_group="all", seed=DEFAULT_SEED, n_splits=N_SPLITS,
                      min_class_count=MIN_CLASS_COUNT, max_request_chars=None):
    """Request sizes per fold before anything is sent. Character counts are exact; tokens are a rough guide.

    Numeric JSON tokenizes at roughly 2-3 characters per token, so the estimate
    divides by 2.5. Check the real count with the provider's tokenizer.
    """
    sizes = []
    for gene, k, fold in iter_folds(dataset, seed, n_splits, min_class_count,
                                    _feature_groups_arg(dataset, feature_group), genes):
        chars = len(json.dumps(build_llm_payload(fold), allow_nan=False))
        sizes.append({"gene": gene, "fold": k, "train_rows": len(fold.train_X), "test_rows": len(fold.test_X),
                      "features": len(fold.feature_names), "request_chars": chars,
                      "rough_request_tokens": int(math.ceil(chars / 2.5))})
    largest = max((s["request_chars"] for s in sizes), default=0)
    return {"folds": sizes, "largest_request_chars": largest,
            "largest_rough_request_tokens": int(math.ceil(largest / 2.5)),
            "max_request_chars": max_request_chars,
            "within_limit": None if max_request_chars is None else largest <= max_request_chars}


# ---------------------------------------------------------------- command line

def synthetic_dataset(n=64, n_features=12, seed=7):
    """Invented rows in the load_dataset() contract, for smoke runs away from the data host."""
    rng = random.Random(seed)
    labels = {}
    for gene, count in (("SYNTH_A", 38), ("SYNTH_B", 12), ("SYNTH_RARE", 2)):
        chosen = set(rng.sample(range(n), count))
        labels[gene] = [int(i in chosen) for i in range(n)]
    X = []
    for i in range(n):
        row = [rng.gauss(0, 1) + 2.0 * labels["SYNTH_A"][i]] + [rng.gauss(0, 1) for _ in range(n_features - 1)]
        if i % 9 == 0:
            row[3] = None
        X.append(row)
    names = [f"synthetic_{j:02d}" for j in range(n_features)]
    return {"case_ids": [f"synthetic-{i:03d}" for i in range(n)], "feature_names": names, "X": X, "labels": labels,
            "feature_groups": {"all": names, "spatial": names[:6], "clinical": names[6:]},
            "metadata": {"source_kind": "synthetic rows generated by prediction_eval.synthetic_dataset; no patients"}}


def command_client(command, timeout=600):
    """A client that pipes the request to a local command's stdin and reads its stdout. No shell."""
    argv = shlex.split(command)

    def client(request):
        done = subprocess.run(argv, input=request, capture_output=True, text=True, timeout=timeout)
        if done.returncode != 0:
            raise RuntimeError("model command exited non-zero")
        return done.stdout
    return client


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--root", type=Path, help="release root for pcnsl.prediction_data.load_dataset (data host only)")
    source.add_argument("--synthetic", action="store_true", help="run on invented rows")
    parser.add_argument("--out", type=Path, required=True, help="aggregate JSON report; never overwritten")
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    parser.add_argument("--feature-groups", nargs="+", default=None)
    parser.add_argument("--genes", nargs="+", default=None)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--tabpfn-model-path", type=Path, default=None, help="local TabPFN checkpoint file")
    parser.add_argument("--tabpfn-device", default=None)
    parser.add_argument("--tabpfn-allow-download", action="store_true",
                        help="let tabpfn fetch its default checkpoint; off by default (offline)")
    parser.add_argument("--llm-command", help="command that reads one request on stdin and prints the response")
    parser.add_argument("--llm-model-label", default="unspecified")
    parser.add_argument("--llm-folds", nargs="+", type=int, default=None, help="prespecified folds for the model arm")
    parser.add_argument("--llm-max-request-chars", type=int, default=None, help="refuse larger requests instead of sending")
    parser.add_argument("--preflight", action="store_true", help="write request sizes only; run no arm and send nothing")
    parser.add_argument("--llm-endpoint-approved", action="store_true",
                        help="required with --root: confirms the command sends rows only to an endpoint approved for this data")
    args = parser.parse_args(argv)
    os.umask(0o077)
    if args.llm_command and args.root and not args.llm_endpoint_approved:
        parser.error("--llm-command with --root needs --llm-endpoint-approved")
    if args.synthetic:
        dataset = synthetic_dataset()
    else:
        try:
            from .prediction_data import load_dataset
        except ImportError:
            from prediction_data import load_dataset
        dataset = load_dataset(args.root, seed=DEFAULT_SEED, min_class_count=MIN_CLASS_COUNT)
    if args.preflight:
        report = payload_preflight(dataset, args.genes, args.feature_groups, max_request_chars=args.llm_max_request_chars)
        with args.out.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False); stream.write("\n")
        print(json.dumps({"complete": True, "preflight": True, "largest_request_chars": report["largest_request_chars"],
                          "within_limit": report["within_limit"]}))
        return 0
    arms = [TabPFNArm(device=args.tabpfn_device, model_path=args.tabpfn_model_path,
                      offline=not args.tabpfn_allow_download) if name == "tabpfn" else ARMS[name]()
            for name in args.arms]
    if args.llm_command:
        arms.append(DirectLLMArm(client=command_client(args.llm_command), model_label=args.llm_model_label,
                                 only_folds=args.llm_folds, max_request_chars=args.llm_max_request_chars))
    report = run_evaluation(dataset, arms, feature_groups=args.feature_groups, genes=args.genes,
                            bootstrap=args.bootstrap)
    report["run"] = {"source": "synthetic" if args.synthetic else "hosted release via prediction_data.load_dataset",
                     "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "python": sys.version.split()[0]}
    with args.out.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write("\n")
    print(json.dumps({"complete": True, "genes": len(report["genes"]),
                      "arm_statuses": {name: entry["statuses"] for name, entry in report["summary"].items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
