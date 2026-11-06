"""Synthetic catchment / drain network definition (data/catchment.json)."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import cop

DATA = Path(__file__).resolve().parents[1] / "data" / "catchment.json"


@dataclass(frozen=True)
class Node:
    id: str
    x: float
    y: float
    ground: float
    outfall: bool = False


@dataclass(frozen=True)
class Reach:
    id: str
    frm: str
    to: str
    length: float
    ground_slope: float
    main: bool


@dataclass(frozen=True)
class Subcatchment:
    id: str
    outlet: str
    land_use: str
    area_ha: float
    fractions: dict
    c: float
    overland_time_min: float
    overland_length_m: float
    slope_pct: float
    rect: tuple


@dataclass
class Network:
    name: str
    nodes: dict[str, Node]
    reaches: list[Reach]                       # topological order (upstream first)
    subcatchments: list[Subcatchment]
    _by_id: dict = field(default_factory=dict, repr=False)

    def reach(self, rid: str) -> Reach:
        return self._by_id[rid]

    def incoming(self, node_id: str) -> list[Reach]:
        return [r for r in self.reaches if r.to == node_id]

    def outgoing(self, node_id: str) -> list[Reach]:
        return [r for r in self.reaches if r.frm == node_id]

    def subs_at(self, node_id: str) -> list[Subcatchment]:
        return [s for s in self.subcatchments if s.outlet == node_id]

    def contributing_subs(self, node_id: str) -> list[Subcatchment]:
        """All sub-catchments draining to node_id (inclusive of local ones)."""
        out = list(self.subs_at(node_id))
        for r in self.incoming(node_id):
            out.extend(self.contributing_subs(r.frm))
        return out

    def main_line(self) -> list[Reach]:
        return [r for r in self.reaches if r.main]

    @property
    def total_area_ha(self) -> float:
        return sum(s.area_ha for s in self.subcatchments)


def _topological(reaches: list[Reach]) -> list[Reach]:
    remaining = list(reaches)
    done_nodes_out: set[str] = set()
    order: list[Reach] = []
    while remaining:
        progressed = False
        for r in list(remaining):
            ups = [u for u in reaches if u.to == r.frm]
            if all(u.id in done_nodes_out for u in ups):
                order.append(r)
                done_nodes_out.add(r.id)
                remaining.remove(r)
                progressed = True
        if not progressed:
            raise ValueError("network has a cycle")
    return order


def load(path: Path = DATA) -> Network:
    with open(path) as f:
        raw = json.load(f)
    nodes = {n["id"]: Node(n["id"], n["x"], n["y"], n["ground"], n.get("outfall", False))
             for n in raw["nodes"]}
    reaches = []
    for r in raw["reaches"]:
        a, b = nodes[r["from"]], nodes[r["to"]]
        length = math.hypot(b.x - a.x, b.y - a.y)
        reaches.append(Reach(r["id"], r["from"], r["to"], length,
                             (a.ground - b.ground) / length, r.get("main", False)))
    subs = []
    for s in raw["subcatchments"]:
        lu = raw["land_use_types"][s["land_use"]]
        fr = {k: lu[k] for k in ("road", "urban", "vegetated")}
        x0, y0, x1, y1 = s["rect"]
        area_ha = (x1 - x0) * (y1 - y0) / 10_000.0
        to = lu["overland_time_min"]
        if not cop.OVERLAND_TIME_MIN <= to <= cop.OVERLAND_TIME_MAX:
            raise ValueError(f"{s['id']}: overland time {to} outside COP 7.1.4 range")
        subs.append(Subcatchment(s["id"], s["outlet"], s["land_use"], area_ha, fr,
                                 cop.weighted_c(fr), to, lu["overland_length_m"],
                                 lu["slope_pct"], tuple(s["rect"])))
    order = _topological(reaches)
    net = Network(raw["name"], nodes, order, subs)
    net._by_id = {r.id: r for r in order}
    return net
