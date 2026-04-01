from __future__ import annotations

from app.workflows.chr.names import CHRWorkflowName


def available_workflows() -> list[str]:
    return [w.value for w in CHRWorkflowName]


def normalize_workflow_name(name: str) -> CHRWorkflowName:
    try:
        return CHRWorkflowName(name)
    except ValueError as exc:
        raise ValueError(f"Unknown workflow {name!r}.") from exc

