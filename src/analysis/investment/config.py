"""Assumption loading for the investment (benefit-cost) analysis.

Every numeric assumption lives in ``data/reference_data/investment_assumptions.yaml``
as a *parameter block*::

    name:
      central: 0.05
      low: 0.03
      high: 0.07
      unit: real p.a.
      source: CRRDC Impact Assessment Guidelines (2018 V2)
      status: verified | snippet | judgement | data

``status`` says how much weight the number can bear:
    verified  - read directly from the cited source
    snippet   - taken from a search extract; the source page could not be opened
    judgement - analyst assumption; must be confirmed before publication
    data      - derived from the trial data or a data file in this repo

The loader refuses a block without ``central``, ``source`` and ``status`` so an
uncited number cannot enter the analysis silently.
"""

from __future__ import annotations

import copy
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

logger = logging.getLogger(__name__)

VALID_STATUS = {"verified", "snippet", "judgement", "data"}
SCENARIOS = ("low", "central", "high")


def default_assumptions_path() -> str:
    return os.path.join("data", "reference_data", "investment_assumptions.yaml")


def _is_param_block(node: Any) -> bool:
    return isinstance(node, dict) and "central" in node


def _validate(node: Any, path: str = "") -> list[str]:
    """Return a list of problems found in the assumption tree."""
    problems: list[str] = []
    if _is_param_block(node):
        for key in ("source", "status"):
            if not node.get(key):
                problems.append(f"{path}: missing '{key}'")
        if node.get("status") and node["status"] not in VALID_STATUS:
            problems.append(f"{path}: status '{node['status']}' not in {sorted(VALID_STATUS)}")
        lo, c, hi = node.get("low"), node.get("central"), node.get("high")
        if all(isinstance(v, (int, float)) for v in (lo, c, hi)) and not (lo <= c <= hi):
            problems.append(f"{path}: expected low <= central <= high, got {lo}, {c}, {hi}")
        return problems
    if isinstance(node, dict):
        for k, v in node.items():
            problems.extend(_validate(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            problems.extend(_validate(v, f"{path}[{i}]"))
    return problems


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and not _is_param_block(v) and isinstance(out.get(k), dict) \
                and not _is_param_block(out[k]):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass
class Assumptions:
    """Parsed assumption tree with scenario-aware accessors."""

    tree: dict
    overrides: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | None = None, profile: str | None = None) -> "Assumptions":
        """Load the assumptions file, optionally overlaid with a named profile.

        A profile is ``investment_assumptions_<profile>.yaml`` beside the base file. Its
        parameter blocks replace the base ones (deep merge); every block it supplies must
        be cited like the base. Used for comparison scenarios such as the RDC
        impact-assessment convention, never to change the central case silently.
        """
        path = path or default_assumptions_path()
        with open(path, encoding="utf-8") as fh:
            tree = yaml.safe_load(fh)
        if profile:
            root, ext = os.path.splitext(path)
            with open(f"{root}_{profile}{ext}", encoding="utf-8") as fh:
                overlay = yaml.safe_load(fh) or {}
            tree = _deep_merge(tree, overlay)
            tree.setdefault("meta", {})["profile"] = profile
        problems = _validate(tree)
        if problems:
            raise ValueError("Invalid assumptions file:\n  " + "\n  ".join(problems))
        return cls(tree=tree)

    # ------------------------------------------------------------------ access
    def node(self, dotted: str) -> Any:
        cur: Any = self.tree
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                raise KeyError(f"assumption '{dotted}' not found (failed at '{part}')")
            cur = cur[part]
        return cur

    def get(self, dotted: str, scenario: str = "central") -> Any:
        """Value of a parameter under a scenario (low/central/high).

        Overrides (set with :meth:`with_overrides`) win over the file.
        Non-parameter nodes are returned unchanged.
        """
        if dotted in self.overrides:
            return self.overrides[dotted]
        n = self.node(dotted)
        if _is_param_block(n):
            if scenario not in SCENARIOS:
                raise ValueError(f"scenario must be one of {SCENARIOS}")
            return n.get(scenario, n["central"])
        return n

    def triple(self, dotted: str) -> tuple[float, float, float]:
        n = self.node(dotted)
        if not _is_param_block(n):
            raise KeyError(f"'{dotted}' is not a parameter block")
        c = n["central"]
        return (n.get("low", c), c, n.get("high", c))

    def with_overrides(self, **dotted_values: Any) -> "Assumptions":
        """Copy with some parameters fixed (keys use '__' or '.' for nesting)."""
        new = Assumptions(tree=copy.deepcopy(self.tree), overrides=dict(self.overrides))
        for k, v in dotted_values.items():
            new.overrides[k.replace("__", ".")] = v
        return new

    def register(self) -> list[dict]:
        """Flat register of every parameter block (for the assumptions table)."""
        rows: list[dict] = []

        def walk(node: Any, path: str) -> None:
            if _is_param_block(node):
                rows.append(
                    {
                        "parameter": path,
                        "low": node.get("low", node["central"]),
                        "central": node["central"],
                        "high": node.get("high", node["central"]),
                        "unit": node.get("unit", ""),
                        "status": node["status"],
                        "source": node["source"],
                        "note": node.get("note", ""),
                    }
                )
            elif isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else str(k))

        walk(self.tree, "")
        return rows
