from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.report import EvidenceRef


class GraphNode(BaseModel):
    node_id: str
    kind: Literal["lab", "biomarker_series", "domain"]
    code: str | None = None
    name: str
    latest_interpretation: Literal["low", "normal", "high"] | None = None
    trend: Literal["increasing", "decreasing", "stable"] | None = None


class GraphEdge(BaseModel):
    src: str
    dst: str
    relation: Literal["belongs_to"] = "belongs_to"


class BiomarkerConcern(BaseModel):
    concern_id: str
    title: str
    statement: str
    severity: Literal["info", "mild", "moderate", "high"] = "info"
    evidence: list[EvidenceRef] = Field(default_factory=list)


class BiomarkerGraph(BaseModel):
    graph_version: Literal["bg_v1"] = "bg_v1"
    generated_at: datetime
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

