from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from app.models.patient import NormalizedBiomarkerSeries, NormalizedLab, NormalizedPatient
from app.models.report import EvidenceRef
from app.workflows.biomarker_graph.models import (
    BiomarkerConcern,
    BiomarkerGraph,
    GraphEdge,
    GraphNode,
)

_DOMAIN_BY_CODE: dict[str, str] = {
    # Lipids
    "LDL_C": "lipids",
    "HDL_C": "lipids",
    "TRIG": "lipids",
    # Glycemic
    "A1C": "glycemic",
    "GLUCOSE": "glycemic",
    # Inflammation
    "HS_CRP": "inflammation",
}


def build_biomarker_graph(
    *, normalized: NormalizedPatient
) -> tuple[BiomarkerGraph, list[BiomarkerConcern]]:
    generated_at = datetime.now(tz=UTC)

    measurement_nodes: list[GraphNode] = []
    measurement_nodes.extend(_lab_nodes(labs=normalized.labs))
    measurement_nodes.extend(_series_nodes(series=normalized.biomarker_series))

    domain_nodes = _domain_nodes(nodes=measurement_nodes)
    edges = _domain_edges(measurement_nodes=measurement_nodes, domain_nodes=domain_nodes)

    nodes = sorted([*measurement_nodes, *domain_nodes], key=lambda n: (n.kind, n.node_id))
    edges = sorted(edges, key=lambda e: (e.src, e.dst, e.relation))

    graph = BiomarkerGraph(generated_at=generated_at, nodes=nodes, edges=edges)
    concerns = _concerns_from_measurements(measurement_nodes=measurement_nodes, normalized=normalized)
    concerns = sorted(concerns, key=lambda c: c.concern_id)
    return graph, concerns


def _lab_nodes(*, labs: Iterable[NormalizedLab]) -> list[GraphNode]:
    nodes: list[GraphNode] = []
    for lab in labs:
        nodes.append(
            GraphNode(
                node_id=lab.lab_id,
                kind="lab",
                code=lab.code,
                name=lab.name,
                latest_interpretation=lab.interpretation,
                trend=None,
            )
        )
    return nodes


def _series_nodes(*, series: Iterable[NormalizedBiomarkerSeries]) -> list[GraphNode]:
    nodes: list[GraphNode] = []
    for s in series:
        nodes.append(
            GraphNode(
                node_id=s.series_id,
                kind="biomarker_series",
                code=s.code,
                name=s.name,
                latest_interpretation=s.latest_interpretation,
                trend=s.trend,
            )
        )
    return nodes


def _domain_nodes(*, nodes: Iterable[GraphNode]) -> list[GraphNode]:
    domains: set[str] = set()
    for n in nodes:
        if n.code is None:
            continue
        domain = _DOMAIN_BY_CODE.get(n.code)
        if domain:
            domains.add(domain)
    return [
        GraphNode(node_id=f"domain:{d}", kind="domain", name=d, code=None) for d in sorted(domains)
    ]


def _domain_edges(
    *, measurement_nodes: Iterable[GraphNode], domain_nodes: Iterable[GraphNode]
) -> list[GraphEdge]:
    domain_ids = {n.name: n.node_id for n in domain_nodes}
    edges: list[GraphEdge] = []
    for n in measurement_nodes:
        if n.code is None:
            continue
        domain = _DOMAIN_BY_CODE.get(n.code)
        if not domain:
            continue
        dst = domain_ids.get(domain)
        if dst:
            edges.append(GraphEdge(src=n.node_id, dst=dst))
    return edges


def _concerns_from_measurements(
    *, measurement_nodes: Iterable[GraphNode], normalized: NormalizedPatient
) -> list[BiomarkerConcern]:
    concerns: list[BiomarkerConcern] = []
    lab_by_id = {lab.lab_id: lab for lab in normalized.labs}
    series_by_id = {s.series_id: s for s in normalized.biomarker_series}

    for n in measurement_nodes:
        if n.kind == "lab":
            if n.latest_interpretation and n.latest_interpretation != "normal":
                lab = lab_by_id.get(n.node_id)
                title = f"Abnormal lab requires review: {n.name}"
                statement = (
                    f"{n.name} ({n.code}) is {n.latest_interpretation} in the synthetic input."
                    if lab is None
                    else (
                        f"{lab.name} ({lab.code}) is {lab.interpretation} at {lab.value} {lab.unit} "
                        f"(reference {lab.ref_range.low}-{lab.ref_range.high} {lab.unit}) "
                        "in the synthetic input."
                    )
                )
                concerns.append(
                    BiomarkerConcern(
                        concern_id=f"concern_lab_{n.node_id}",
                        title=title,
                        statement=statement,
                        severity="moderate",
                        evidence=[EvidenceRef(kind="lab", id=n.node_id)],
                    )
                )
            continue

        if n.kind == "biomarker_series":
            s = series_by_id.get(n.node_id)
            if s is None or not s.points:
                continue

            if n.latest_interpretation and n.latest_interpretation != "normal":
                latest_value = s.points[-1].value
                title = f"Abnormal biomarker series requires review: {n.name}"
                statement = (
                    f"{n.name} ({n.code}) latest value is {latest_value} {s.unit} "
                    f"({s.latest_interpretation}), trend is {s.trend}, in the synthetic input."
                )
                concerns.append(
                    BiomarkerConcern(
                        concern_id=f"concern_series_{n.node_id}",
                        title=title,
                        statement=statement,
                        severity="moderate",
                        evidence=[EvidenceRef(kind="biomarker_series", id=n.node_id)],
                    )
                )
                continue

            if n.trend == "increasing":
                title = f"Rising biomarker trend for inspection: {n.name}"
                statement = (
                    f"{n.name} ({n.code}) trend is increasing based on {len(s.points)} "
                    "synthetic measurement(s)."
                )
                concerns.append(
                    BiomarkerConcern(
                        concern_id=f"concern_series_trend_{n.node_id}",
                        title=title,
                        statement=statement,
                        severity="mild",
                        evidence=[EvidenceRef(kind="biomarker_series", id=n.node_id)],
                    )
                )

    return concerns

