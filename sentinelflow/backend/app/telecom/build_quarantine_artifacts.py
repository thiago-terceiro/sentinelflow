"""Deterministic builder & verifier for SF-010 dataset quarantine and assessment artifacts.

Reconstructs ``uci_sms_spam_secondary.json`` and ``external_source_assessment.json`` from pinned
immutable upstream sources (or verified local archives) using strict AST-based corpus extraction,
canonical LF JSON serialization, and timestamp-independent content hashing.

Strictly isolated from ONNX runtime, training pipelines, model inference, and heuristic scoring.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zipfile import ZipFile

import httpx
from app.telecom.dataset_quarantine import (
    FROZEN_DEV_VAL_DATASET_SHA256,
    FROZEN_ONNX_MODEL_SHA256,
    FROZEN_TRAINING_DATASET_SHA256,
    assess_holdout_suitability,
    compute_canonical_content_digest,
    compute_overlap_audit,
    get_dataset_governance_paths,
    normalize_line_endings_lf,
    normalized_sha256,
    parse_uci_sms_spam_collection,
    serialize_canonical_json_lf_bytes,
    sha256_bytes,
    sha256_text,
    verify_uci_artifact_integrity,
)

UCI_CANONICAL_PORTAL_URL = "https://archive.ics.uci.edu/dataset/228/sms+spam+collection"
UCI_ZIP_URL = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
UCI_EXPECTED_ZIP_SHA256 = "1587ea43e58e82b14ff1f5425c88e17f8496bfcdb67a583dbff9eefaf9963ce3"
UCI_EXPECTED_MEMBERS: tuple[str, ...] = ("SMSSpamCollection", "readme")
UCI_EXPECTED_MEMBER_SHA256: dict[str, str] = {
    "SMSSpamCollection": "7d039a24a6083ed9ef0f806ebad56bbb976e3aeb8de05669173bfdc4996c239d",
    "readme": "8753cd2d3cab68f80c8257851b8c2037778c267f55accb6fd1b5a2e32d36a84e",
}

IMC25_PINNED_COMMIT = "a6175560b57387199871e51fbef6bc523d2516b4"
IMC25_CANONICAL_REPO_URL = "https://github.com/reportsmishing/Smishing-Dataset-IMC25"
IMC25_PINNED_RAW_URL = (
    "https://raw.githubusercontent.com/reportsmishing/Smishing-Dataset-IMC25/"
    f"{IMC25_PINNED_COMMIT}/dataset/final_dataset_output.csv"
)
IMC25_EXPECTED_CSV_SHA256 = "1bbd1e9e82c3ea023112207b80da268a5c4a07d2353c2b0898360ab037fa9a64"

ALLOWED_UPSTREAM_HOSTS: frozenset[str] = frozenset(
    {"archive.ics.uci.edu", "raw.githubusercontent.com"}
)
URL_PLACEHOLDER_TAG = "<URL>"
PRESIDIO_TAG_RE = re.compile(r"<[A-Z0-9_]+>")
RAW_HTTP_URL_RE = re.compile(r"https?://", re.IGNORECASE)


class _BreakSignal(Exception):
    """Internal control-flow signal for pure-AST loop break."""


class _ContinueSignal(Exception):
    """Internal control-flow signal for pure-AST loop continue."""


class _ReturnSignal(Exception):
    """Internal control-flow signal for pure-AST function return."""

    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value


class _HashlibSha256Proxy:
    """Minimal safe read-only proxy for hashlib inside pure-AST evaluation."""

    @staticmethod
    def sha256(data: bytes) -> Any:
        return hashlib.sha256(data)


class _ReModuleProxy:
    """Minimal safe read-only proxy for stdlib re inside pure-AST evaluation."""

    @staticmethod
    def sub(pattern: str, repl: str, string: str, count: int = 0) -> str:
        return re.sub(pattern, repl, string, count=count)

    @staticmethod
    def match(pattern: str, string: str) -> re.Match[str] | None:
        return re.match(pattern, string)

    @staticmethod
    def search(pattern: str, string: str) -> re.Match[str] | None:
        return re.search(pattern, string)

    @staticmethod
    def findall(pattern: str, string: str) -> list[Any]:
        return re.findall(pattern, string)

    @staticmethod
    def compile(pattern: str) -> re.Pattern[str]:
        return re.compile(pattern)


class _PureAstFunction:
    """Callable wrapper around an allowlisted pure-Python AST function definition."""

    def __init__(
        self,
        func_node: ast.FunctionDef,
        evaluator: _PureAstEvaluator,
        closure_scope: dict[str, Any],
        defaults: list[Any],
        kw_defaults: list[Any | None],
    ) -> None:
        self.func_node = func_node
        self.evaluator = evaluator
        self.closure_scope = closure_scope
        self.defaults = defaults
        self.kw_defaults = kw_defaults

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        local_scope: dict[str, Any] = {}
        pos_args = list(self.func_node.args.posonlyargs) + list(self.func_node.args.args)
        num_pos = len(pos_args)
        num_required = num_pos - len(self.defaults)

        for idx, arg_def in enumerate(pos_args):
            name = arg_def.arg
            if idx < len(args):
                if name in kwargs:
                    raise TypeError(f"Multiple values for argument {name!r}")
                local_scope[name] = args[idx]
            elif name in kwargs:
                local_scope[name] = kwargs.pop(name)
            elif idx >= num_required:
                local_scope[name] = self.defaults[idx - num_required]
            else:
                raise TypeError(f"Missing required argument {name!r}")

        if len(args) > num_pos:
            raise TypeError(f"{self.func_node.name}() takes at most {num_pos} positional args")

        for kw_arg, kw_default in zip(
            self.func_node.args.kwonlyargs,
            self.kw_defaults,
            strict=True,
        ):
            name = kw_arg.arg
            if name in kwargs:
                local_scope[name] = kwargs.pop(name)
            elif kw_default is not None:
                local_scope[name] = kw_default
            else:
                raise TypeError(f"Missing required keyword-only argument {name!r}")

        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(f"Unexpected keyword arguments: {unexpected}")

        try:
            for stmt in self.func_node.body:
                self.evaluator.exec_stmt(stmt, local_scope, parent_scope=self.closure_scope)
        except _ReturnSignal as ret:
            return ret.value
        return None


class _PureAstEvaluator:
    """Safe recursive AST evaluator over a tightly constrained pure-Python subset.

    Never executes arbitrary imports, subprocesses, file/network I/O, or ``eval``/``exec``.
    Resolves referenced module-level definitions lazily so unrelated ML/ONNX module definitions
    are never touched during corpus verification.
    """

    _SAFE_BUILTINS: dict[str, Any] = {
        "True": True,
        "False": False,
        "None": None,
        "range": range,
        "enumerate": enumerate,
        "len": len,
        "list": list,
        "tuple": tuple,
        "set": set,
        "dict": dict,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "chr": chr,
        "ord": ord,
        "zip": zip,
        "sorted": sorted,
        "min": min,
        "max": max,
        "sum": sum,
        "any": any,
        "all": all,
        "isinstance": isinstance,
        "ValueError": ValueError,
        "RuntimeError": RuntimeError,
    }
    _SAFE_STR_METHODS = frozenset(
        {
            "lower",
            "upper",
            "strip",
            "lstrip",
            "rstrip",
            "replace",
            "format",
            "split",
            "join",
            "startswith",
            "endswith",
            "encode",
        }
    )
    _SAFE_CONTAINER_METHODS: dict[type[Any], frozenset[str]] = {
        list: frozenset({"append", "extend", "copy"}),
        set: frozenset({"add", "update", "copy"}),
        dict: frozenset({"get", "items", "keys", "values", "setdefault", "copy"}),
        bytes: frozenset({"decode"}),
    }

    def __init__(self, source_text: str) -> None:
        tree = ast.parse(source_text)
        self._top_defs: dict[str, ast.AST] = {}
        self._resolved: dict[str, Any] = {
            "hashlib": _HashlibSha256Proxy(),
            "re": _ReModuleProxy(),
        }
        self._resolving: set[str] = set()

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self._top_defs[node.name] = node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._top_defs[target.id] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is not None:
                    self._top_defs[node.target.id] = node.value

    def get_symbol(self, name: str) -> Any:
        """Lazily evaluates and returns an exported top-level symbol or function."""
        if name in self._resolved:
            return self._resolved[name]
        if name in self._SAFE_BUILTINS:
            return self._SAFE_BUILTINS[name]
        if name not in self._top_defs:
            raise NameError(f"Symbol {name!r} is not defined in module AST")
        if name in self._resolving:
            raise RuntimeError(f"Cyclic AST symbol dependency detected for {name!r}")

        self._resolving.add(name)
        try:
            node = self._top_defs[name]
            if isinstance(node, ast.FunctionDef):
                value = self._bind_function(node, scope={})
            else:
                value = self.eval_expr(node, scope={})
            self._resolved[name] = value
            return value
        finally:
            self._resolving.discard(name)

    def _lookup_name(
        self,
        name: str,
        scope: dict[str, Any],
        parent_scope: dict[str, Any] | None = None,
    ) -> Any:
        if name in scope:
            return scope[name]
        if parent_scope is not None and name in parent_scope:
            return parent_scope[name]
        return self.get_symbol(name)

    def _bind_function(
        self,
        node: ast.FunctionDef,
        scope: dict[str, Any],
        parent_scope: dict[str, Any] | None = None,
    ) -> _PureAstFunction:
        closure = dict(parent_scope or {})
        closure.update(scope)
        defaults = [self.eval_expr(d, scope, parent_scope) for d in node.args.defaults]
        kw_defaults = [
            None if d is None else self.eval_expr(d, scope, parent_scope)
            for d in node.args.kw_defaults
        ]
        return _PureAstFunction(node, self, closure, defaults, kw_defaults)

    def _assign_target(self, target: ast.AST, value: Any, scope: dict[str, Any]) -> None:
        if isinstance(target, ast.Name):
            scope[target.id] = value
            return
        if isinstance(target, ast.Tuple | ast.List):
            items = list(value)
            if len(items) != len(target.elts):
                raise ValueError(
                    f"Cannot unpack {len(items)} items into {len(target.elts)} targets"
                )
            for sub_target, sub_val in zip(target.elts, items, strict=True):
                self._assign_target(sub_target, sub_val, scope)
            return
        raise ValueError(f"Unsupported AST assignment target: {ast.dump(target)}")

    def exec_stmt(
        self,
        stmt: ast.AST,
        scope: dict[str, Any],
        parent_scope: dict[str, Any] | None = None,
    ) -> None:
        """Executes a single allowlisted statement inside ``scope``."""
        if isinstance(stmt, ast.Pass):
            return
        if isinstance(stmt, ast.Expr):
            self.eval_expr(stmt.value, scope, parent_scope)
            return
        if isinstance(stmt, ast.Assign):
            val = self.eval_expr(stmt.value, scope, parent_scope)
            for target in stmt.targets:
                self._assign_target(target, val, scope)
            return
        if isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None:
                val = self.eval_expr(stmt.value, scope, parent_scope)
                self._assign_target(stmt.target, val, scope)
            return
        if isinstance(stmt, ast.AugAssign):
            if not isinstance(stmt.target, ast.Name):
                raise ValueError(f"Unsupported AugAssign target: {ast.dump(stmt.target)}")
            cur = self._lookup_name(stmt.target.id, scope, parent_scope)
            rhs = self.eval_expr(stmt.value, scope, parent_scope)
            scope[stmt.target.id] = self._apply_binop(stmt.op, cur, rhs)
            return
        if isinstance(stmt, ast.Return):
            ret_val = (
                None if stmt.value is None else self.eval_expr(stmt.value, scope, parent_scope)
            )
            raise _ReturnSignal(ret_val)
        if isinstance(stmt, ast.Break):
            raise _BreakSignal()
        if isinstance(stmt, ast.Continue):
            raise _ContinueSignal()
        if isinstance(stmt, ast.If):
            branch = (
                stmt.body
                if self.eval_expr(stmt.test, scope, parent_scope)
                else stmt.orelse
            )
            for sub in branch:
                self.exec_stmt(sub, scope, parent_scope)
            return
        if isinstance(stmt, ast.For):
            iterable = self.eval_expr(stmt.iter, scope, parent_scope)
            for item in iterable:
                self._assign_target(stmt.target, item, scope)
                try:
                    for sub in stmt.body:
                        self.exec_stmt(sub, scope, parent_scope)
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    break
            else:
                for sub in stmt.orelse:
                    self.exec_stmt(sub, scope, parent_scope)
            return
        if isinstance(stmt, ast.FunctionDef):
            scope[stmt.name] = self._bind_function(stmt, scope, parent_scope)
            return
        if isinstance(stmt, ast.Raise):
            exc = (
                self.eval_expr(stmt.exc, scope, parent_scope)
                if stmt.exc
                else RuntimeError("AST raise")
            )
            if isinstance(exc, BaseException):
                raise exc
            raise RuntimeError(str(exc))
        raise ValueError(f"Unsupported AST statement node: {type(stmt).__name__}")

    def eval_expr(
        self,
        expr: ast.AST,
        scope: dict[str, Any],
        parent_scope: dict[str, Any] | None = None,
    ) -> Any:
        """Evaluates an allowlisted pure expression AST node."""
        if isinstance(expr, ast.Constant):
            return expr.value
        if isinstance(expr, ast.Name):
            return self._lookup_name(expr.id, scope, parent_scope)
        if isinstance(expr, ast.List):
            return [self.eval_expr(elt, scope, parent_scope) for elt in expr.elts]
        if isinstance(expr, ast.Tuple):
            return tuple(self.eval_expr(elt, scope, parent_scope) for elt in expr.elts)
        if isinstance(expr, ast.Set):
            return {self.eval_expr(elt, scope, parent_scope) for elt in expr.elts}
        if isinstance(expr, ast.Dict):
            return {
                self.eval_expr(k, scope, parent_scope): self.eval_expr(v, scope, parent_scope)
                for k, v in zip(expr.keys, expr.values, strict=True)
                if k is not None
            }
        if isinstance(expr, ast.JoinedStr):
            parts = [str(self.eval_expr(v, scope, parent_scope)) for v in expr.values]
            return "".join(parts)
        if isinstance(expr, ast.FormattedValue):
            val = self.eval_expr(expr.value, scope, parent_scope)
            if expr.format_spec is not None:
                spec = str(self.eval_expr(expr.format_spec, scope, parent_scope))
                return format(val, spec)
            return str(val)
        if isinstance(expr, ast.BinOp):
            left = self.eval_expr(expr.left, scope, parent_scope)
            right = self.eval_expr(expr.right, scope, parent_scope)
            return self._apply_binop(expr.op, left, right)
        if isinstance(expr, ast.UnaryOp):
            val = self.eval_expr(expr.operand, scope, parent_scope)
            if isinstance(expr.op, ast.UAdd):
                return +val
            if isinstance(expr.op, ast.USub):
                return -val
            if isinstance(expr.op, ast.Not):
                return not val
            raise ValueError(f"Unsupported unary op: {type(expr.op).__name__}")
        if isinstance(expr, ast.BoolOp):
            if isinstance(expr.op, ast.And):
                result: Any = True
                for item in expr.values:
                    result = self.eval_expr(item, scope, parent_scope)
                    if not result:
                        return result
                return result
            result = False
            for item in expr.values:
                result = self.eval_expr(item, scope, parent_scope)
                if result:
                    return result
            return result
        if isinstance(expr, ast.Compare):
            return self._eval_compare(expr, scope, parent_scope)
        if isinstance(expr, ast.IfExp):
            cond = self.eval_expr(expr.test, scope, parent_scope)
            target = expr.body if cond else expr.orelse
            return self.eval_expr(target, scope, parent_scope)
        if isinstance(expr, ast.Subscript):
            obj = self.eval_expr(expr.value, scope, parent_scope)
            if isinstance(expr.slice, ast.Slice):
                low = (
                    None
                    if expr.slice.lower is None
                    else self.eval_expr(expr.slice.lower, scope, parent_scope)
                )
                high = (
                    None
                    if expr.slice.upper is None
                    else self.eval_expr(expr.slice.upper, scope, parent_scope)
                )
                step = (
                    None
                    if expr.slice.step is None
                    else self.eval_expr(expr.slice.step, scope, parent_scope)
                )
                return obj[slice(low, high, step)]
            idx = self.eval_expr(expr.slice, scope, parent_scope)
            return obj[idx]
        if isinstance(expr, ast.ListComp | ast.SetComp | ast.GeneratorExp):
            items = list(self._eval_comprehension(expr.elt, expr.generators, scope, parent_scope))
            if isinstance(expr, ast.SetComp):
                return set(items)
            return items
        if isinstance(expr, ast.DictComp):
            out: dict[Any, Any] = {}
            pairs = self._eval_dict_comp(
                expr.key, expr.value, expr.generators, scope, parent_scope
            )
            for k, v in pairs:
                out[k] = v
            return out
        if isinstance(expr, ast.Attribute):
            obj = self.eval_expr(expr.value, scope, parent_scope)
            return self._safe_attr(obj, expr.attr)
        if isinstance(expr, ast.Call):
            return self._eval_call(expr, scope, parent_scope)
        raise ValueError(f"Unsupported AST expression node: {type(expr).__name__}")

    def _safe_attr(self, obj: Any, attr: str) -> Any:
        if attr.startswith("_"):
            raise ValueError(f"Disallowed private attribute access: {attr!r}")
        if isinstance(obj, str) and attr in self._SAFE_STR_METHODS:
            return getattr(obj, attr)
        for cls, allowed in self._SAFE_CONTAINER_METHODS.items():
            if isinstance(obj, cls) and attr in allowed:
                return getattr(obj, attr)
        if isinstance(obj, _HashlibSha256Proxy) and attr == "sha256":
            return obj.sha256
        if isinstance(obj, _ReModuleProxy) and attr in {
            "sub",
            "match",
            "search",
            "findall",
            "compile",
        }:
            return getattr(obj, attr)
        if isinstance(obj, re.Pattern) and attr in {"search", "match", "findall", "sub"}:
            return getattr(obj, attr)
        if type(obj).__name__ == "HASH" and attr in {"hexdigest", "digest"}:
            return getattr(obj, attr)
        raise ValueError(f"Disallowed AST attribute {type(obj).__name__}.{attr}")

    def _eval_call(
        self,
        expr: ast.Call,
        scope: dict[str, Any],
        parent_scope: dict[str, Any] | None,
    ) -> Any:
        func = self.eval_expr(expr.func, scope, parent_scope)
        pos_args: list[Any] = []
        for arg in expr.args:
            if isinstance(arg, ast.Starred):
                pos_args.extend(self.eval_expr(arg.value, scope, parent_scope))
            else:
                pos_args.append(self.eval_expr(arg, scope, parent_scope))
        kw_args: dict[str, Any] = {}
        for kw in expr.keywords:
            if kw.arg is None:
                kw_args.update(self.eval_expr(kw.value, scope, parent_scope))
            else:
                kw_args[kw.arg] = self.eval_expr(kw.value, scope, parent_scope)
        return func(*pos_args, **kw_args)

    def _eval_comprehension(
        self,
        elt: ast.AST,
        generators: list[ast.comprehension],
        scope: dict[str, Any],
        parent_scope: dict[str, Any] | None,
    ) -> list[Any]:
        results: list[Any] = []
        comp_scope = dict(scope)

        def _recurse(gen_idx: int) -> None:
            if gen_idx >= len(generators):
                results.append(self.eval_expr(elt, comp_scope, parent_scope))
                return
            gen = generators[gen_idx]
            iterable = self.eval_expr(gen.iter, comp_scope, parent_scope)
            for item in iterable:
                self._assign_target(gen.target, item, comp_scope)
                if all(self.eval_expr(cond, comp_scope, parent_scope) for cond in gen.ifs):
                    _recurse(gen_idx + 1)

        _recurse(0)
        return results

    def _eval_dict_comp(
        self,
        key_expr: ast.AST,
        val_expr: ast.AST,
        generators: list[ast.comprehension],
        scope: dict[str, Any],
        parent_scope: dict[str, Any] | None,
    ) -> list[tuple[Any, Any]]:
        results: list[tuple[Any, Any]] = []
        comp_scope = dict(scope)

        def _recurse(gen_idx: int) -> None:
            if gen_idx >= len(generators):
                k = self.eval_expr(key_expr, comp_scope, parent_scope)
                v = self.eval_expr(val_expr, comp_scope, parent_scope)
                results.append((k, v))
                return
            gen = generators[gen_idx]
            iterable = self.eval_expr(gen.iter, comp_scope, parent_scope)
            for item in iterable:
                self._assign_target(gen.target, item, comp_scope)
                if all(self.eval_expr(cond, comp_scope, parent_scope) for cond in gen.ifs):
                    _recurse(gen_idx + 1)

        _recurse(0)
        return results

    @staticmethod
    def _apply_binop(op: ast.operator, left: Any, right: Any) -> Any:
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.Mod):
            return left % right
        raise ValueError(f"Unsupported binary operator: {type(op).__name__}")

    def _eval_compare(
        self,
        expr: ast.Compare,
        scope: dict[str, Any],
        parent_scope: dict[str, Any] | None,
    ) -> bool:
        left = self.eval_expr(expr.left, scope, parent_scope)
        for op, comparator in zip(expr.ops, expr.comparators, strict=True):
            right = self.eval_expr(comparator, scope, parent_scope)
            ok = self._compare_pair(op, left, right)
            if not ok:
                return False
            left = right
        return True

    @staticmethod
    def _compare_pair(op: ast.cmpop, left: Any, right: Any) -> bool:
        if isinstance(op, ast.Eq):
            return bool(left == right)
        if isinstance(op, ast.NotEq):
            return bool(left != right)
        if isinstance(op, ast.Lt):
            return bool(left < right)
        if isinstance(op, ast.LtE):
            return bool(left <= right)
        if isinstance(op, ast.Gt):
            return bool(left > right)
        if isinstance(op, ast.GtE):
            return bool(left >= right)
        if isinstance(op, ast.In):
            return bool(left in right)
        if isinstance(op, ast.NotIn):
            return bool(left not in right)
        if isinstance(op, ast.Is):
            return left is right
        if isinstance(op, ast.IsNot):
            return left is not right
        raise ValueError(f"Unsupported comparison op: {type(op).__name__}")


def extract_frozen_corpora(telecom_dir: Path | None = None) -> dict[str, Any]:
    """Extracts frozen Train (N=703) and Dev/Val (N=400) corpora strictly via pure AST parsing."""
    base_dir = (telecom_dir or Path(__file__).resolve().parent).resolve()
    train_source = (base_dir / "train_onnx_model.py").read_text(encoding="utf-8")
    eval_source = (base_dir / "evaluate_model.py").read_text(encoding="utf-8")

    train_eval = _PureAstEvaluator(train_source)
    train_texts, train_labels, _ = train_eval.get_symbol("build_augmented_dataset")()

    dev_eval = _PureAstEvaluator(eval_source)
    dev_val_texts, dev_val_labels = dev_eval.get_symbol("get_held_out_evaluation_set")()

    train_sha = sha256_text(
        "".join(f"{t}:{lbl}" for t, lbl in zip(train_texts, train_labels, strict=True))
    )
    dev_val_sha = sha256_text(
        "".join(f"{t}:{lbl}" for t, lbl in zip(dev_val_texts, dev_val_labels, strict=True))
    )
    if train_sha != FROZEN_TRAINING_DATASET_SHA256:
        raise ValueError(
            f"Extracted Train corpus hash {train_sha} != frozen {FROZEN_TRAINING_DATASET_SHA256}"
        )
    if dev_val_sha != FROZEN_DEV_VAL_DATASET_SHA256:
        raise ValueError(
            f"Extracted Dev/Val corpus hash {dev_val_sha} != frozen {FROZEN_DEV_VAL_DATASET_SHA256}"
        )

    onnx_sha = sha256_bytes((base_dir / "models" / "sms_fraud_model.onnx").read_bytes())
    if onnx_sha != FROZEN_ONNX_MODEL_SHA256:
        raise ValueError(f"Frozen ONNX hash {onnx_sha} != expected {FROZEN_ONNX_MODEL_SHA256}")

    return {
        "train_texts": [str(t) for t in train_texts],
        "train_labels": [int(lbl) for lbl in train_labels],
        "train_sha256": train_sha,
        "dev_val_texts": [str(t) for t in dev_val_texts],
        "dev_val_labels": [int(lbl) for lbl in dev_val_labels],
        "dev_val_sha256": dev_val_sha,
        "onnx_sha256": onnx_sha,
    }


def fetch_verified_bytes(
    *,
    url: str,
    expected_sha256: str,
    local_path: Path | None = None,
    timeout_seconds: float = 60.0,
) -> bytes:
    """Loads upstream artifact bytes from local path or HTTPS URL with SHA-256 verification."""
    if local_path is not None:
        data = local_path.read_bytes()
    else:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_UPSTREAM_HOSTS:
            raise ValueError(f"Blocked unpinned upstream URL: {url}")
        response = httpx.get(url, follow_redirects=True, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.content

    actual_sha = sha256_bytes(data)
    if actual_sha != expected_sha256:
        source_label = str(local_path) if local_path is not None else url
        raise ValueError(
            f"Checksum mismatch for {source_label}: {actual_sha} != {expected_sha256}"
        )
    return data


def extract_verified_uci_members(zip_bytes: bytes) -> dict[str, bytes]:
    """Safely extracts allowlisted members from UCI #228 ZIP and verifies SHA-256 hashes."""
    if sha256_bytes(zip_bytes) != UCI_EXPECTED_ZIP_SHA256:
        raise ValueError("UCI ZIP SHA-256 mismatch before member extraction")

    extracted: dict[str, bytes] = {}
    with ZipFile(io.BytesIO(zip_bytes)) as archive:
        member_names = archive.namelist()
        if set(member_names) != set(UCI_EXPECTED_MEMBERS):
            raise ValueError(
                f"Unexpected UCI ZIP members: {sorted(member_names)} != "
                f"{sorted(UCI_EXPECTED_MEMBERS)}"
            )
        for member in UCI_EXPECTED_MEMBERS:
            member_bytes = archive.read(member)
            actual = sha256_bytes(member_bytes)
            expected = UCI_EXPECTED_MEMBER_SHA256[member]
            if actual != expected:
                raise ValueError(f"UCI member {member!r} SHA-256 {actual} != {expected}")
            extracted[member] = member_bytes
    return extracted


def _summarize_imc25_subset(subset: list[dict[str, Any]]) -> dict[str, Any]:
    seen_unique: dict[str, str] = {}
    for row in subset:
        seen_unique.setdefault(str(row["normalized_sha256"]), str(row["text"]))
    unique_texts = list(seen_unique.values())
    all_texts = [str(row["text"]) for row in subset]
    return {
        "row_count": len(all_texts),
        "unique_normalized_count": len(unique_texts),
        "unique_with_url_placeholder": sum(URL_PLACEHOLDER_TAG in t for t in unique_texts),
        "unique_with_raw_http_url": sum(bool(RAW_HTTP_URL_RE.search(t)) for t in unique_texts),
        "unique_without_any_presidio_tag": sum(not PRESIDIO_TAG_RE.search(t) for t in unique_texts),
        "total_with_url_placeholder": sum(URL_PLACEHOLDER_TAG in t for t in all_texts),
        "total_with_raw_http_url": sum(bool(RAW_HTTP_URL_RE.search(t)) for t in all_texts),
        "total_without_any_presidio_tag": sum(not PRESIDIO_TAG_RE.search(t) for t in all_texts),
    }


def compute_imc25_verified_evidence(
    csv_bytes: bytes,
    *,
    train_texts: list[str],
    dev_val_texts: list[str],
) -> dict[str, Any]:
    """Recomputes exact IMC25 counts, URL/redaction stats, and overlap vs Train & Dev/Val."""
    actual_sha = sha256_bytes(csv_bytes)
    if actual_sha != IMC25_EXPECTED_CSV_SHA256:
        raise ValueError(f"IMC25 CSV SHA-256 mismatch: {actual_sha} != {IMC25_EXPECTED_CSV_SHA256}")

    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    if (
        reader.fieldnames is None
        or "text" not in reader.fieldnames
        or "scam_type" not in reader.fieldnames
    ):
        raise ValueError(f"Unexpected IMC25 CSV schema headers: {reader.fieldnames}")
    all_rows = list(reader)

    english_rows: list[dict[str, Any]] = []
    non_spam_all: list[dict[str, Any]] = []
    non_spam_named: list[dict[str, Any]] = []
    empty_scam_type_csv_rows: list[int] = []
    scam_type_counts: Counter[str] = Counter()

    for csv_row_num, row in enumerate(all_rows, start=1):
        if row.get("language") != "English":
            continue
        text = str(row.get("text") or "")
        scam_type = str(row.get("scam_type") or "")
        key = scam_type if scam_type else "empty"
        scam_type_counts[key] += 1
        rec = {
            "upstream_record_id": f"imc25_row_{csv_row_num}",
            "original_label": key,
            "text": text,
            "normalized_sha256": normalized_sha256(text),
            "scam_type": scam_type,
            "csv_row": csv_row_num,
        }
        english_rows.append(rec)
        if scam_type != "spam":
            non_spam_all.append(rec)
            if scam_type == "":
                empty_scam_type_csv_rows.append(csv_row_num)
            else:
                non_spam_named.append(rec)

    all_non_spam_stats = _summarize_imc25_subset(non_spam_all)
    named_non_spam_stats = _summarize_imc25_subset(non_spam_named)
    overlap = compute_overlap_audit(
        english_rows,
        train_texts=train_texts,
        dev_val_texts=dev_val_texts,
        near_threshold=0.45,
    )

    ordered_counts = {
        k: int(scam_type_counts[k])
        for k in sorted(scam_type_counts, key=lambda name: (-scam_type_counts[name], name))
    }

    verified_counts = {
        "total_multilingual_records": len(all_rows),
        "english_records": len(english_rows),
        "english_by_scam_type": ordered_counts,
        "non_spam_inclusion_rule": (
            "language == 'English' and scam_type != 'spam' "
            "(explicitly includes 1 non-spam record with empty scam_type at CSV data row 33411 "
            "which retains lure_principles='distraction,time/urgency')."
        ),
        "english_non_spam_smishing_total": all_non_spam_stats["row_count"],
        "english_non_spam_unique_normalized": all_non_spam_stats["unique_normalized_count"],
        "english_non_spam_empty_scam_type_count": len(empty_scam_type_csv_rows),
        "english_non_spam_empty_scam_type_csv_rows": empty_scam_type_csv_rows,
        "english_named_non_spam_smishing_total": named_non_spam_stats["row_count"],
        "english_named_non_spam_unique_normalized": named_non_spam_stats["unique_normalized_count"],
        "english_non_spam_with_url_placeholder": all_non_spam_stats[
            "unique_with_url_placeholder"
        ],
        "english_non_spam_with_raw_http_url": all_non_spam_stats["unique_with_raw_http_url"],
        "english_non_spam_without_any_presidio_tag": all_non_spam_stats[
            "unique_without_any_presidio_tag"
        ],
        "english_non_spam_total_rows_with_url_placeholder": all_non_spam_stats[
            "total_with_url_placeholder"
        ],
        "english_non_spam_total_rows_with_raw_http_url": all_non_spam_stats[
            "total_with_raw_http_url"
        ],
        "english_non_spam_total_rows_without_any_presidio_tag": all_non_spam_stats[
            "total_without_any_presidio_tag"
        ],
    }
    overlap_summary = {
        "english_exact_matches_train": overlap["against_train"]["exact_text_matches"],
        "english_normalized_matches_train": overlap["against_train"]["normalized_sha256_matches"],
        "english_max_word_3gram_jaccard_train": overlap["against_train"]["max_word_3gram_jaccard"],
        "english_word_3gram_near_ge_045_train": overlap["against_train"][
            "word_3gram_near_duplicate_count"
        ],
        "english_unigram_near_ge_045_train": overlap["against_train"][
            "unigram_near_duplicate_count"
        ],
        "english_exact_matches_dev_val": overlap["against_dev_val"]["exact_text_matches"],
        "english_normalized_matches_dev_val": overlap["against_dev_val"][
            "normalized_sha256_matches"
        ],
        "english_max_word_3gram_jaccard_dev_val": overlap["against_dev_val"][
            "max_word_3gram_jaccard"
        ],
        "english_word_3gram_near_ge_045_dev_val": overlap["against_dev_val"][
            "word_3gram_near_duplicate_count"
        ],
        "english_max_unigram_jaccard_dev_val": overlap["against_dev_val"]["max_unigram_jaccard"],
        "english_unigram_near_ge_045_dev_val": overlap["against_dev_val"][
            "unigram_near_duplicate_count"
        ],
    }
    return {
        "raw_artifact_sha256": actual_sha,
        "file_format": f"CSV (UTF-8, 12 columns, {len(csv_bytes):,} bytes)",
        "verified_counts": verified_counts,
        "overlap_audit_summary": overlap_summary,
    }


MANUAL_CANDIDATE_ADJUDICATIONS: dict[str, dict[str, Any]] = {
    "imc25_smishing_reports": {
        "candidate_id": "imc25_smishing_reports",
        "name": "Fishing for Smishing: Labeled Smishing Dataset (IMC '25)",
        "stable_id": f"github:reportsmishing/Smishing-Dataset-IMC25@{IMC25_PINNED_COMMIT}",
        "canonical_url": IMC25_CANONICAL_REPO_URL,
        "retrieval_url": IMC25_PINNED_RAW_URL,
        "paper_doi": "10.1145/3730567.3764431",
        "publisher": "Agarwal, Papasavva, Suarez-Tangil & Vasek (ACM IMC 2025)",
        "publication_date_or_version": f"2025-09-12T15:53:16Z (commit {IMC25_PINNED_COMMIT})",
        "license": "CC BY 4.0 (verified LICENSE.txt and README.md)",
        "license_caveats": (
            "Requires attribution under CC BY 4.0; no publisher-signed checksum file provided."
        ),
        "checksum_provenance": "locally_computed_identity_fingerprint",
        "source_population": (
            "Public user-submitted smishing reports mined from online reporting forums/social "
            "feeds (e.g. Reddit) globally"
        ),
        "collection_method": (
            "Programmatic scraping and OCR/text extraction of public smishing report posts with "
            "upstream NER PII redaction"
        ),
        "geography_and_period": (
            "Global (top non-empty English networks: IND=3,657, USA=1,492, GBR=798, AUS=447, "
            "CAN=180; reported period includes 2023+ campaigns)"
        ),
        "original_label_taxonomy": {
            "scam_type": (
                "Categorical attack theme across banking, others, government, delivery, telecom, "
                "spam, wrong number, hey mum/dad (plus 1 unlabeled non-spam English row)"
            ),
            "lure_principles": "Persuasion cue annotations",
        },
        "record_id_scheme": "CSV 1-based row index (no explicit publisher UUID column)",
        "suitability_gates": {
            "legal_and_license_clear": True,
            "observed_external_provenance": True,
            "fraud_smishing_label_fidelity": True,
            "two_class_benign_negative_balance": False,
            "verbatim_or_unconfounded_feature_fidelity": False,
        },
        "retained_role": "rejected_as_standalone_primary_holdout_documented_positive_caveat",
        "decision": "NOT INGESTED INTO PRIMARY HOLDOUT",
        "rejection_or_limitation_reasons": [
            (
                "Positive-only dataset (0 genuine legitimate/benign SMS negatives): cannot "
                "measure FPR, Specificity, Precision, Tier-2 false blocks, or two-class ROC-AUC."
            ),
            (
                "Pairing 2023+ Presidio-redacted IMC25 positives against 2002-2011 unredacted UCI "
                "ham negatives creates fatal domain, era, and placeholder-token confounding."
            ),
            (
                "Heavy upstream NER redaction (<URL> in 6,030/14,363 unique non-spam English "
                "rows, <DATE_TIME>, <PHONE_NUMBER>, false <US_DRIVER_LICENSE> tags) strips raw "
                "URL domains and callback numbers inspected by SentinelPulse heuristics, breaking "
                "verbatim evaluation."
            ),
        ],
    },
    "uci_sms_spam_collection_v1": {
        "candidate_id": "uci_sms_spam_collection_v1",
        "name": "UCI SMS Spam Collection v.1",
        "stable_id": "uci:228/sms-spam-collection-v1",
        "canonical_url": UCI_CANONICAL_PORTAL_URL,
        "retrieval_url": UCI_ZIP_URL,
        "paper_doi": "10.1145/2034691.2034742",
        "publisher": "UCI ML Repository / Almeida, Gomez Hidalgo & Yamakami (ACM DocEng 2011)",
        "publication_date_or_version": "2011 (corpus v.1)",
        "license": "CC BY 4.0 (UCI Dataset #228 portal)",
        "license_caveats": (
            "Bundled readme Section 4 specifies copyright by Almeida & Gomez Hidalgo, citation "
            "request, no warranty, and user indemnity."
        ),
        "checksum_provenance": "locally_computed_identity_fingerprint",
        "file_format": "ZIP containing TSV text file SMSSpamCollection (477,907 bytes) + readme",
        "source_population": (
            "Mixed public/research UK Grumbletext forum spam claims (425), Caroline Tagg PhD ham "
            "(450), NUS SMS Corpus student chat (3,375 ham), Gomez Hidalgo corpus (1,002 ham, "
            "322 spam)"
        ),
        "collection_method": (
            "Manual extraction from public UK spam complaint forum merged with "
            "university/volunteer SMS collections"
        ),
        "geography_and_period": "UK & Singapore (ca. 2002-2011)",
        "original_label_taxonomy": {
            "ham": "Legitimate conversational SMS (4,827 records)",
            "spam": "Generic unsolicited commercial/prize/ringtone SMS spam (747 records)",
        },
        "record_id_scheme": "1-based line number uci_228_line_<1..5574>",
        "suitability_gates": {
            "legal_and_license_clear": True,
            "observed_external_provenance": True,
            "fraud_smishing_label_fidelity": False,
            "two_class_benign_negative_balance": True,
            "verbatim_or_unconfounded_feature_fidelity": False,
        },
        "retained_role": "secondary_legacy_spam_transfer_benchmark",
        "quarantined_artifact": "uci_sms_spam_secondary.json",
        "decision": (
            "RETAINED STRICTLY AS SECONDARY LEGACY SPAM TRANSFER BENCHMARK (NO FRAUD RELABELING)"
        ),
        "rejection_or_limitation_reasons": [
            (
                "Original labels represent legacy ham vs commercial spam, NOT financial "
                "fraud/smishing; relabeling spam->fraud or ham->benign is prohibited."
            ),
            (
                "Contains 415 intra-corpus normalized duplicate rows (5,159 unique texts across "
                "5,574 rows; 0 label conflicts)."
            ),
            (
                "2002-2011 domain/era mismatch vs modern A2P transactional banking, 2FA, "
                "Zelle/Venmo, and broken-phone WhatsApp smishing."
            ),
        ],
    },
    "mendeley_f45bkkt8pr_v1": {
        "candidate_id": "mendeley_f45bkkt8pr_v1",
        "name": "SMS Phishing Dataset for Machine Learning and Pattern Recognition",
        "stable_id": "doi:10.17632/f45bkkt8pr.1",
        "canonical_url": "https://data.mendeley.com/datasets/f45bkkt8pr",
        "retrieval_url": (
            "https://data.mendeley.com/public-files/datasets/f45bkkt8pr/files/"
            "edb361de-918d-469f-9106-e84823830665/file_downloaded"
        ),
        "paper_doi": None,
        "publisher": "Sandhya Mishra & Devpriya Soni (Mendeley Data)",
        "publication_date_or_version": "2022-06-20T07:15:01.344Z (v1)",
        "retrieval_timestamp_utc": "2026-11-10T22:50:20+00:00",
        "license": "CC BY 4.0 (with third-party content rights notice)",
        "license_caveats": (
            "Mendeley CC BY 4.0 notice explicitly warns further permission may be required for "
            "third-party content; scrapes third-party Pinterest images."
        ),
        "checksum_provenance": "locally_computed_identity_fingerprint",
        "raw_artifact_sha256": "9bbf3188fdad81495d8e82825648b9b63b53fc86841a3d26c02629990b233cc3",
        "file_format": "ZIP containing Dataset_5971.csv (244,698 bytes zip)",
        "source_population": (
            "Hybrid blend of 2011 UCI SMS Spam Collection rows + OCR-converted Pinterest scam "
            "image screenshots"
        ),
        "collection_method": "Exact copying of UCI ham/spam combined with Python OCR on web images",
        "geography_and_period": "Mixed / Undocumented web images + 2002-2011 UCI base",
        "original_label_taxonomy": {
            "ham": "4,844 rows",
            "Smishing/smishing": "638 rows (616 'Smishing' + 22 'smishing')",
            "spam/Spam": "489 rows (466 'spam' + 23 'Spam')",
        },
        "verified_counts": {
            "total_records": 5971,
            "uci_exact_normalized_overlap_breakdown": {
                "ham_matching_uci_ham": 4319,
                "spam_matching_uci_spam": 345,
                "smishing_matching_uci_spam_RELABELED": 361,
            },
        },
        "record_id_scheme": "None (unindexed CSV rows without original source IDs)",
        "suitability_gates": {
            "legal_and_license_clear": False,
            "observed_external_provenance": False,
            "fraud_smishing_label_fidelity": False,
            "two_class_benign_negative_balance": False,
            "verbatim_or_unconfounded_feature_fidelity": False,
        },
        "retained_role": "rejected",
        "decision": "REJECTED (SEVERE CONTAMINATION & UNVERIFIED PROVENANCE)",
        "rejection_or_limitation_reasons": [
            (
                "Forensic audit verified 361 of 638 'Smishing' rows (56.6%) are exact copies of "
                "2011 UCI 'spam' rows silently relabeled as Smishing."
            ),
            (
                "4,319 of 4,844 'ham' rows are exact UCI 'ham' duplicates; remaining non-UCI "
                "smishing strings lack source URLs and OCR fidelity validation."
            ),
            (
                "Third-party copyright notice for scraped Pinterest screenshots leaves "
                "redistribution unclear."
            ),
        ],
    },
    "mendeley_vmg875v4xs_v1": {
        "candidate_id": "mendeley_vmg875v4xs_v1",
        "name": (
            "A Balanced Dataset for Spam and Smishing Detection using Large Language Models (LLMs)"
        ),
        "stable_id": "doi:10.17632/vmg875v4xs.1",
        "canonical_url": "https://data.mendeley.com/datasets/vmg875v4xs",
        "retrieval_url": "https://data.mendeley.com/public-api/datasets/vmg875v4xs",
        "paper_doi": None,
        "publisher": "Munoz & Islam (Mendeley Data)",
        "publication_date_or_version": "2025-07-04T15:14:54.627Z (v1)",
        "retrieval_timestamp_utc": "2026-11-10T22:51:10+00:00",
        "license": "CC BY 4.0",
        "license_caveats": (
            "Metadata API inspected cleanly; full data zip not ingested because dataset is "
            "LLM-synthesized."
        ),
        "checksum_provenance": "not_ingested_synthetic_rejection",
        "raw_artifact_sha256": None,
        "file_format": "Tabular SMS dataset on Mendeley",
        "source_population": (
            "LLM-generated / balanced corpus (3,397 ham, 3,397 spam, 3,397 smishing)"
        ),
        "collection_method": "Explicitly documented as created using a Large Language Model (LLM)",
        "geography_and_period": "Synthetic (2025)",
        "original_label_taxonomy": {"ham": 3397, "spam": 3397, "smishing": 3397},
        "verified_counts": {"declared_total": 10191},
        "record_id_scheme": "N/A",
        "suitability_gates": {
            "legal_and_license_clear": True,
            "observed_external_provenance": False,
            "fraud_smishing_label_fidelity": False,
            "two_class_benign_negative_balance": False,
            "verbatim_or_unconfounded_feature_fidelity": False,
        },
        "retained_role": "rejected",
        "decision": "REJECTED (SYNTHETIC LLM-GENERATED CORPUS)",
        "rejection_or_limitation_reasons": [
            (
                "Not externally observed human/carrier SMS traffic: generated via LLM "
                "training/sampling and fails the observed-data provenance requirement."
            )
        ],
    },
    "smishtank_codaspy24": {
        "candidate_id": "smishtank_codaspy24",
        "name": "Smishing Dataset I: Phishing SMS Dataset from Smishtank.com",
        "stable_id": "arxiv:2402.18430v1",
        "canonical_url": "https://arxiv.org/abs/2402.18430",
        "retrieval_url": "https://smishtank.com/dataset",
        "paper_doi": "10.1145/3626232.3653282",
        "publisher": "Daniel Timko & Muhammad Lutfor Rahman (CSU San Marcos / ACM CODASPY '24)",
        "publication_date_or_version": "2024-02-28 (arXiv:2402.18430v1)",
        "retrieval_timestamp_utc": "2026-11-10T22:52:01+00:00",
        "license": "UNCLEAR / CC BY-NC-SA 4.0 on arXiv paper",
        "license_caveats": (
            "arXiv preprint specifies CC BY-NC-SA 4.0 (NonCommercial); direct dataset URL "
            "https://smishtank.com/dataset failed HTTP retrieval (unreachable) with no open "
            "dataset license verified."
        ),
        "checksum_provenance": "unavailable_inaccessible_endpoint",
        "raw_artifact_sha256": None,
        "file_format": "Reported 1,090-sample CSV in paper",
        "source_population": "Crowdsourced user submissions to Smishtank.com",
        "collection_method": "Screenshot/text public user reports",
        "geography_and_period": "Primarily US/English community reports (ca. 2023-2024)",
        "original_label_taxonomy": {
            "smishing": "1,090 reported smishing messages (positive-only per paper abstract)"
        },
        "verified_counts": {"paper_reported_smishing_samples": 1090, "benign_samples": 0},
        "record_id_scheme": "Unknown (dataset endpoint inaccessible)",
        "suitability_gates": {
            "legal_and_license_clear": False,
            "observed_external_provenance": True,
            "fraud_smishing_label_fidelity": True,
            "two_class_benign_negative_balance": False,
            "verbatim_or_unconfounded_feature_fidelity": False,
        },
        "retained_role": "rejected",
        "decision": "REJECTED (INACCESSIBLE ENDPOINT, UNCLEAR/NC LICENSE, POSITIVE-ONLY)",
        "rejection_or_limitation_reasons": [
            (
                "Direct source URL https://smishtank.com/dataset was unreachable during audit, "
                "preventing verified checksum/schema inspection; third-party student GitHub "
                "mirrors lack upstream license authorization."
            ),
            (
                "Paper preprint carries CC BY-NC-SA 4.0 and positive-only corpus has 0 benign "
                "negatives."
            ),
        ],
    },
    "zenodo_15235123_multiclass_phishing": {
        "candidate_id": "zenodo_15235123_multiclass_phishing",
        "name": "Multiclass NLP Dataset for Phishing and Social Engineering Threat Detection",
        "stable_id": "doi:10.5281/zenodo.15235123",
        "canonical_url": "https://zenodo.org/records/15235123",
        "retrieval_url": (
            "https://zenodo.org/api/records/15235123/files/phishing_nlp_dataset.xlsx/content"
        ),
        "paper_doi": "10.5281/zenodo.15235123",
        "publisher": "Engineering Ingegneria Informatica Spa (Zenodo)",
        "publication_date_or_version": "2025-04-17",
        "retrieval_timestamp_utc": "2026-11-10T22:50:55+00:00",
        "license": "CC BY 4.0",
        "license_caveats": "Open CC BY 4.0 on Zenodo; anonymized without upstream source URLs.",
        "checksum_provenance": (
            "locally_computed_sha256_plus_zenodo_md5_7213a3ee515a713f4eee2a6948f1756e"
        ),
        "raw_artifact_sha256": "651fb58e1a3ff7808aad12eb5a24a44dc0ba95a4f4da356640d17a830dd8bd32",
        "file_format": "XLSX (51,291 bytes, 625 spreadsheet rows including header)",
        "source_population": (
            "Mixed email/SMS-like corpus dominated by multi-paragraph Nigerian 419/advance-fee "
            "emails"
        ),
        "collection_method": "Undocumented upstream collection/anonymization",
        "geography_and_period": "Undocumented (published Apr 2025)",
        "original_label_taxonomy": {
            "classes": [
                "Phishing",
                "Malware",
                "Scareware",
                "Baiting",
                "Pretexting",
                "NOT-Malicious",
            ]
        },
        "verified_counts": {"xlsx_rows_excl_header": 624},
        "record_id_scheme": "Spreadsheet row number (no upstream SMS ID)",
        "suitability_gates": {
            "legal_and_license_clear": True,
            "observed_external_provenance": False,
            "fraud_smishing_label_fidelity": False,
            "two_class_benign_negative_balance": True,
            "verbatim_or_unconfounded_feature_fidelity": False,
        },
        "retained_role": "rejected",
        "decision": "REJECTED (CHANNEL MISMATCH: EMAIL ESSAYS & UNDOCUMENTED PROVENANCE)",
        "rejection_or_limitation_reasons": [
            (
                "Inspected spreadsheet rows contain multi-paragraph email bodies ('Power of "
                "Attorney... reply via fax... on his email') rather than real telecom SMS traffic."
            ),
            "Record metadata omits source channel, collection dates, and upstream origin.",
        ],
    },
    "github_shaghayegh_combined_smishing": {
        "candidate_id": "github_shaghayegh_combined_smishing",
        "name": "Combined Labeled Smishing Dataset (shaghayegh-hp/Smishing_Dataset)",
        "stable_id": "github:shaghayegh-hp/Smishing_Dataset",
        "canonical_url": "https://github.com/shaghayegh-hp/Smishing_Dataset",
        "retrieval_url": "https://api.github.com/repos/shaghayegh-hp/Smishing_Dataset",
        "paper_doi": "10.1145/3734477.3736147",
        "publisher": "Shaghayegh Hosseinpour (GitHub)",
        "publication_date_or_version": "Unversioned main branch (8,749,929 bytes CSV)",
        "retrieval_timestamp_utc": "2026-11-10T22:51:11+00:00",
        "license": (
            "NONE (no LICENSE file; README grants informal 'academic and research purposes' only)"
        ),
        "license_caveats": (
            "No valid OSI/Creative Commons redistribution license; merges 5 unattributed upstream "
            "datasets."
        ),
        "checksum_provenance": "not_ingested_license_and_label_rejection",
        "raw_artifact_sha256": None,
        "file_format": "CSV",
        "source_population": "Ad-hoc merge of 5 unspecified public SMS datasets",
        "collection_method": (
            "README states 'Messages are relabeled based on the presence of frequent "
            "smishing-related keywords'"
        ),
        "geography_and_period": "Unspecified",
        "original_label_taxonomy": {
            "spam label": "0/1",
            "smishing label": "0/1 (keyword-relabeled)",
        },
        "verified_counts": {"file_size_bytes": 8749929},
        "record_id_scheme": "None",
        "suitability_gates": {
            "legal_and_license_clear": False,
            "observed_external_provenance": False,
            "fraud_smishing_label_fidelity": False,
            "two_class_benign_negative_balance": False,
            "verbatim_or_unconfounded_feature_fidelity": False,
        },
        "retained_role": "rejected",
        "decision": "REJECTED (NO LICENSE & CIRCULAR KEYWORD-HEURISTIC RELABELING)",
        "rejection_or_limitation_reasons": [
            (
                "Violates Phase 1 legal clarity (license: None on repository; mixes 5 upstream "
                "datasets without clearing third-party licenses)."
            ),
            (
                "Violates Phase 2 label integrity: relabels smishing heuristically from keyword "
                "presence rather than verified incident ground truth."
            ),
        ],
    },
    "hf_gandharvbakshi_otp_phishing": {
        "candidate_id": "hf_gandharvbakshi_otp_phishing",
        "name": "SMS-dataset-OTP-OTP_INTENT_Phishing (HuggingFace)",
        "stable_id": "hf:gandharvbakshi/SMS-dataset-OTP-OTP_INTENT_Phishing",
        "canonical_url": (
            "https://huggingface.co/datasets/gandharvbakshi/SMS-dataset-OTP-OTP_INTENT_Phishing"
        ),
        "retrieval_url": (
            "https://huggingface.co/datasets/gandharvbakshi/SMS-dataset-OTP-OTP_INTENT_Phishing/"
            "resolve/main/sample_10k.csv"
        ),
        "paper_doi": None,
        "publisher": "Gandharv Bakshi (Hugging Face Hub)",
        "publication_date_or_version": "Unversioned Hub repo",
        "retrieval_timestamp_utc": "2026-11-10T22:53:01+00:00",
        "license": (
            "CONFLICTING (YAML tag says 'mit', README restricts full dataset via gated access & "
            "private commercial licensing DM)"
        ),
        "license_caveats": (
            "Full file returns HTTP 401 Unauthorized; README states 'Synthetic + Labeled Indian "
            "SMS Dataset' and requests email/DM for commercial licensing."
        ),
        "checksum_provenance": "not_ingested_gated_and_synthetic",
        "raw_artifact_sha256": None,
        "file_format": "CSV (gated HTTP 401)",
        "source_population": "Synthetic + LLM-classified Indian OTP/phishing texts",
        "collection_method": (
            "Includes 'classification_results_with_phishing_llm_balanced_with_sender.csv' "
            "(LLM synthetic/labeled)"
        ),
        "geography_and_period": "Synthetic / India",
        "original_label_taxonomy": {
            "predicted_is_otp": "boolean",
            "phishing_labeling": "unspecified LLM pipeline",
        },
        "verified_counts": {"readme_claimed_rows": 73470},
        "record_id_scheme": "None",
        "suitability_gates": {
            "legal_and_license_clear": False,
            "observed_external_provenance": False,
            "fraud_smishing_label_fidelity": False,
            "two_class_benign_negative_balance": False,
            "verbatim_or_unconfounded_feature_fidelity": False,
        },
        "retained_role": "rejected",
        "decision": "REJECTED (SYNTHETIC ORIGIN & GATED HTTP 401 LICENSE CONFLICT)",
        "rejection_or_limitation_reasons": [
            (
                "Explicitly identifies as 'Synthetic' and 'phishing_llm_balanced', failing "
                "observed external telemetry provenance."
            ),
            (
                "Gated HTTP 401 download with contradictory MIT tag vs private commercial "
                "licensing requirement."
            ),
        ],
    },
}

CANDIDATE_ORDER: tuple[str, ...] = (
    "imc25_smishing_reports",
    "uci_sms_spam_collection_v1",
    "mendeley_f45bkkt8pr_v1",
    "mendeley_vmg875v4xs_v1",
    "smishtank_codaspy24",
    "zenodo_15235123_multiclass_phishing",
    "github_shaghayegh_combined_smishing",
    "hf_gandharvbakshi_otp_phishing",
)


def build_artifacts_payload(
    *,
    telecom_dir: Path | None = None,
    uci_zip_path: Path | None = None,
    imc25_csv_path: Path | None = None,
    retrieval_timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Reconstructs both UCI quarantine JSON and external source assessment from pinned inputs."""
    ts_utc = retrieval_timestamp_utc or datetime.now(UTC).isoformat()
    if not ts_utc.endswith("+00:00"):
        raise ValueError(f"retrieval_timestamp_utc must end with '+00:00', got {ts_utc!r}")

    corpora = extract_frozen_corpora(telecom_dir)
    uci_zip_bytes = fetch_verified_bytes(
        url=UCI_ZIP_URL,
        expected_sha256=UCI_EXPECTED_ZIP_SHA256,
        local_path=uci_zip_path,
    )
    uci_members = extract_verified_uci_members(uci_zip_bytes)
    uci_bundle = parse_uci_sms_spam_collection(
        uci_members["SMSSpamCollection"],
        source_zip_sha256=UCI_EXPECTED_ZIP_SHA256,
        readme_sha256=UCI_EXPECTED_MEMBER_SHA256["readme"],
        retrieval_utc=ts_utc,
        train_texts=corpora["train_texts"],
        dev_val_texts=corpora["dev_val_texts"],
    )
    uci_lf_bytes = serialize_canonical_json_lf_bytes(uci_bundle)
    uci_lf_sha256 = sha256_bytes(uci_lf_bytes)

    imc25_csv_bytes = fetch_verified_bytes(
        url=IMC25_PINNED_RAW_URL,
        expected_sha256=IMC25_EXPECTED_CSV_SHA256,
        local_path=imc25_csv_path,
    )
    imc25_evidence = compute_imc25_verified_evidence(
        imc25_csv_bytes,
        train_texts=corpora["train_texts"],
        dev_val_texts=corpora["dev_val_texts"],
    )

    uci_manifest = uci_bundle["manifest"]
    uci_overlap = uci_manifest["overlap_audit"]

    imc25_entry = dict(MANUAL_CANDIDATE_ADJUDICATIONS["imc25_smishing_reports"])
    imc25_entry["retrieval_timestamp_utc"] = ts_utc
    imc25_entry["raw_artifact_sha256"] = imc25_evidence["raw_artifact_sha256"]
    imc25_entry["file_format"] = imc25_evidence["file_format"]
    imc25_entry["verified_counts"] = imc25_evidence["verified_counts"]
    imc25_entry["overlap_audit_summary"] = imc25_evidence["overlap_audit_summary"]

    uci_entry = dict(MANUAL_CANDIDATE_ADJUDICATIONS["uci_sms_spam_collection_v1"])
    uci_entry["retrieval_timestamp_utc"] = ts_utc
    uci_entry["raw_artifact_sha256"] = UCI_EXPECTED_ZIP_SHA256
    uci_entry["verified_counts"] = uci_manifest["verified_counts"]
    uci_entry["overlap_audit_summary"] = {
        "exact_matches_train": uci_overlap["against_train"]["exact_text_matches"],
        "normalized_matches_train": uci_overlap["against_train"]["normalized_sha256_matches"],
        "max_word_3gram_jaccard_train": uci_overlap["against_train"]["max_word_3gram_jaccard"],
        "exact_matches_dev_val": uci_overlap["against_dev_val"]["exact_text_matches"],
        "normalized_matches_dev_val": uci_overlap["against_dev_val"]["normalized_sha256_matches"],
        "max_word_3gram_jaccard_dev_val": uci_overlap["against_dev_val"]["max_word_3gram_jaccard"],
    }
    uci_entry["quarantined_artifact_sha256"] = uci_lf_sha256
    uci_entry["quarantined_artifact_canonical_content_sha256"] = uci_manifest[
        "canonical_content_sha256"
    ]
    uci_entry["quarantined_artifact_canonical_rows_sha256"] = uci_manifest["canonical_rows_sha256"]

    computed_overrides = {
        "imc25_smishing_reports": imc25_entry,
        "uci_sms_spam_collection_v1": uci_entry,
    }
    candidates = [
        computed_overrides.get(cid, dict(MANUAL_CANDIDATE_ADJUDICATIONS[cid]))
        for cid in CANDIDATE_ORDER
    ]

    preliminary_assessment: dict[str, Any] = {"candidates": candidates}
    gate_summary = assess_holdout_suitability(preliminary_assessment)

    assessment: dict[str, Any] = {
        "schema_version": "1.1.0",
        "ticket_id": "SF-010R",
        "assessed_at_utc": ts_utc,
        "frozen_baseline_locks": {
            "onnx_model_sha256": corpora["onnx_sha256"],
            "training_dataset_sha256": corpora["train_sha256"],
            "dev_val_dataset_sha256": corpora["dev_val_sha256"],
        },
        "primary_external_holdout_status": gate_summary["primary_holdout_status"],
        "primary_external_holdout_artifact": None,
        "sf_011_status": gate_summary["sf_011_status"],
        "secondary_transfer_benchmark_artifact": "uci_sms_spam_secondary.json",
        "secondary_transfer_benchmark_sha256": uci_lf_sha256,
        "secondary_transfer_benchmark_lf_sha256": uci_lf_sha256,
        "secondary_transfer_benchmark_content_sha256": uci_manifest["canonical_content_sha256"],
        "secondary_transfer_benchmark_canonical_rows_sha256": uci_manifest["canonical_rows_sha256"],
        "provenance_separation": {
            "programmatically_computed_fields": [
                (
                    "frozen_baseline_locks (verified against AST-extracted Train N=703, Dev/Val "
                    "N=400, and disk ONNX bytes)"
                ),
                (
                    "secondary_transfer_benchmark_sha256 / _lf_sha256 / _content_sha256 / "
                    "_canonical_rows_sha256"
                ),
                "candidates[uci_sms_spam_collection_v1].verified_counts & overlap_audit_summary",
                "candidates[imc25_smishing_reports].verified_counts & overlap_audit_summary",
                "gate_summary (computed by dataset_quarantine.assess_holdout_suitability)",
            ],
            "manual_candidate_adjudications": [
                (
                    "Licensing, caveats, and qualitative domain/provenance gate decisions across "
                    "all 8 candidates"
                ),
                (
                    "External static inspection records preserved verbatim for non-ingested "
                    "candidates (Mendeley f45bkkt8pr/vmg875v4xs, Smishtank, Zenodo 15235123, "
                    "GitHub shaghayegh-hp, HuggingFace gandharvbakshi)"
                ),
            ],
        },
        "evidence_classes": {
            "Class A": (
                "Train OOF CV - 703 curated messages across 56 semantic families (SHA-256 "
                f"{FROZEN_TRAINING_DATASET_SHA256}); verified from repository "
                "dataset_inventory.json."
            ),
            "Class B": (
                "Dev/Val Benchmark - 400 messages (200 hard benign, 200 adversarial smishing; "
                f"SHA-256 {FROZEN_DEV_VAL_DATASET_SHA256}); development-exposed, NOT an unseen "
                "external holdout."
            ),
            "Class C": (
                "External Public Evaluation - UNAVAILABLE / BLOCKED for primary SMS "
                "fraud/smishing holdout. Secondary legacy generic spam transfer benchmark (UCI "
                "SMS Spam Collection v.1, 5,574 ham/spam messages) retained separately in "
                "uci_sms_spam_secondary.json and NEVER pooled with fraud metrics."
            ),
            "Class D": (
                "Production Telemetry - FUTURE / UNIMPLEMENTED carrier/SMSC/optical-tap feed; zero "
                "real-world CDR-linked production samples exist in this repository."
            ),
        },
        "gate_summary": gate_summary,
        "candidates": candidates,
    }
    assessment_lf_bytes = serialize_canonical_json_lf_bytes(assessment)

    return {
        "uci_bundle": uci_bundle,
        "uci_lf_bytes": uci_lf_bytes,
        "uci_lf_sha256": uci_lf_sha256,
        "assessment": assessment,
        "assessment_lf_bytes": assessment_lf_bytes,
        "assessment_lf_sha256": sha256_bytes(assessment_lf_bytes),
    }


def write_artifacts_to_directory(
    output_dir: Path,
    built: dict[str, Any],
    *,
    write_canonical: bool = False,
    telecom_dir: Path | None = None,
) -> dict[str, Path]:
    """Writes canonical LF JSON artifacts to ``output_dir`` with canonical overwrite guard."""
    resolved_out = output_dir.resolve()
    gov_paths = get_dataset_governance_paths(telecom_dir)
    canonical_dir = gov_paths["datasets_dir"].resolve()

    if resolved_out == canonical_dir and not write_canonical:
        raise ValueError(
            "Refusing to overwrite canonical repository artifacts in "
            f"{canonical_dir} without --write-canonical"
        )

    resolved_out.mkdir(parents=True, exist_ok=True)
    uci_path = resolved_out / "uci_sms_spam_secondary.json"
    assessment_path = resolved_out / "external_source_assessment.json"

    uci_path.write_bytes(built["uci_lf_bytes"])
    assessment_path.write_bytes(built["assessment_lf_bytes"])
    return {"uci_path": uci_path, "assessment_path": assessment_path}


def verify_repository_reproducibility(
    *,
    telecom_dir: Path | None = None,
    uci_zip_path: Path | None = None,
    imc25_csv_path: Path | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    """Independently verifies committed SF-010/SF-010R artifacts and optional reconstruction."""
    gov_paths = get_dataset_governance_paths(telecom_dir)
    corpora = extract_frozen_corpora(telecom_dir)

    uci_raw_bytes = gov_paths["secondary_uci"].read_bytes()
    assessment_raw_bytes = gov_paths["source_assessment"].read_bytes()
    assessment_lf_bytes = normalize_line_endings_lf(assessment_raw_bytes)
    assessment = json.loads(assessment_lf_bytes.decode("utf-8"))

    uci_integrity = verify_uci_artifact_integrity(
        uci_raw_bytes,
        expected_canonical_lf_sha256=assessment["secondary_transfer_benchmark_sha256"],
    )
    if b"\r\n" in uci_raw_bytes:
        raise ValueError(
            "Committed uci_sms_spam_secondary.json must use canonical LF line endings"
        )
    if b"\r\n" in assessment_raw_bytes:
        raise ValueError(
            "Committed external_source_assessment.json must use canonical LF line endings"
        )

    simulated_crlf = uci_raw_bytes.replace(b"\n", b"\r\n")
    crlf_check = verify_uci_artifact_integrity(
        simulated_crlf,
        expected_canonical_lf_sha256=assessment["secondary_transfer_benchmark_sha256"],
    )
    if crlf_check["lf_canonical_sha256"] != uci_integrity["lf_canonical_sha256"]:
        raise ValueError("Simulated CRLF normalization failed to match canonical LF hash")
    if crlf_check["canonical_content_sha256"] != uci_integrity["canonical_content_sha256"]:
        raise ValueError("Simulated CRLF content digest mismatch")

    root_doc_bytes = gov_paths["governance_root"].read_bytes()
    mirror_doc_bytes = gov_paths["governance_mirror"].read_bytes()
    if root_doc_bytes != mirror_doc_bytes:
        raise ValueError("Mirrored provenance governance markdown files are not byte-identical")

    gate_recomputed = assess_holdout_suitability(assessment)
    if gate_recomputed != assessment["gate_summary"]:
        raise ValueError("assessment['gate_summary'] does not match assess_holdout_suitability()")

    report: dict[str, Any] = {
        "offline": offline,
        "frozen_onnx_sha256": corpora["onnx_sha256"],
        "frozen_train_sha256": corpora["train_sha256"],
        "frozen_dev_val_sha256": corpora["dev_val_sha256"],
        "uci_disk_eol": uci_integrity["eol_style_on_disk"],
        "uci_lf_sha256": uci_integrity["lf_canonical_sha256"],
        "uci_canonical_rows_sha256": uci_integrity["canonical_rows_sha256"],
        "uci_canonical_content_sha256": uci_integrity["canonical_content_sha256"],
        "assessment_lf_sha256": sha256_bytes(assessment_lf_bytes),
        "governance_docs_sha256": sha256_bytes(root_doc_bytes),
        "reconstruction_verified": False,
    }

    if not offline or (uci_zip_path is not None and imc25_csv_path is not None):
        ts_on_disk = str(assessment["assessed_at_utc"])
        built_same_ts = build_artifacts_payload(
            telecom_dir=telecom_dir,
            uci_zip_path=uci_zip_path,
            imc25_csv_path=imc25_csv_path,
            retrieval_timestamp_utc=ts_on_disk,
        )
        with tempfile.TemporaryDirectory(prefix="sf010r_verify_") as tmp_dir:
            written = write_artifacts_to_directory(
                Path(tmp_dir),
                built_same_ts,
                write_canonical=False,
                telecom_dir=telecom_dir,
            )
            rebuilt_uci_bytes = written["uci_path"].read_bytes()
            rebuilt_assessment_bytes = written["assessment_path"].read_bytes()

        if sha256_bytes(rebuilt_uci_bytes) != uci_integrity["lf_canonical_sha256"]:
            raise ValueError(
                "Reconstructed UCI LF bytes do not match committed uci_sms_spam_secondary.json"
            )
        if sha256_bytes(rebuilt_assessment_bytes) != report["assessment_lf_sha256"]:
            raise ValueError(
                "Reconstructed assessment LF bytes do not match committed "
                "external_source_assessment.json"
            )

        # Also prove timestamp invariance with a distinct timestamp
        alt_built = build_artifacts_payload(
            telecom_dir=telecom_dir,
            uci_zip_path=uci_zip_path,
            imc25_csv_path=imc25_csv_path,
            retrieval_timestamp_utc="2099-01-01T00:00:00+00:00",
        )
        alt_content_sha = compute_canonical_content_digest(alt_built["uci_bundle"])
        if alt_content_sha != uci_integrity["canonical_content_sha256"]:
            raise ValueError(
                "Timestamp-independent canonical_content_sha256 varied when timestamp changed"
            )
        report["reconstruction_verified"] = True

    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministically build and verify SF-010 dataset quarantine artifacts."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Target directory where LF-serialized JSON artifacts should be written.",
    )
    parser.add_argument(
        "--write-canonical",
        action="store_true",
        help="Required confirmation flag to overwrite committed canonical files in datasets/.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify committed repository artifacts and reconstruct in a temporary directory.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Used with --verify to skip live HTTPS downloads when local inputs are omitted.",
    )
    parser.add_argument(
        "--uci-zip-path",
        type=Path,
        default=None,
        help="Optional local path to verified UCI sms+spam+collection.zip.",
    )
    parser.add_argument(
        "--imc25-csv-path",
        type=Path,
        default=None,
        help="Optional local path to verified IMC25 final_dataset_output.csv.",
    )
    parser.add_argument(
        "--retrieval-timestamp-utc",
        type=str,
        default=None,
        help="Optional explicit UTC ISO-8601 timestamp ending with '+00:00'.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for deterministic reconstruction and verification."""
    args = _parse_args(argv)
    if not args.verify and args.output_dir is None:
        raise SystemExit("Specify --verify or --output-dir <path>")

    if args.output_dir is not None:
        built = build_artifacts_payload(
            uci_zip_path=args.uci_zip_path,
            imc25_csv_path=args.imc25_csv_path,
            retrieval_timestamp_utc=args.retrieval_timestamp_utc,
        )
        written = write_artifacts_to_directory(
            args.output_dir,
            built,
            write_canonical=args.write_canonical,
        )
        print(
            json.dumps(
                {
                    "uci_path": str(written["uci_path"]),
                    "uci_lf_sha256": built["uci_lf_sha256"],
                    "uci_canonical_rows_sha256": built["uci_bundle"]["manifest"][
                        "canonical_rows_sha256"
                    ],
                    "uci_canonical_content_sha256": built["uci_bundle"]["manifest"][
                        "canonical_content_sha256"
                    ],
                    "assessment_path": str(written["assessment_path"]),
                    "assessment_lf_sha256": built["assessment_lf_sha256"],
                },
                indent=2,
            )
        )

    if args.verify:
        report = verify_repository_reproducibility(
            uci_zip_path=args.uci_zip_path,
            imc25_csv_path=args.imc25_csv_path,
            offline=args.offline,
        )
        print(json.dumps(report, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
