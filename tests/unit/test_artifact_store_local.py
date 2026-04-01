from __future__ import annotations

from pathlib import Path

from app.storage.artifact_store import LocalArtifactStore


def test_local_artifact_store_writes_files_and_returns_refs(tmp_path: Path) -> None:
    store = LocalArtifactStore(root_dir=str(tmp_path)).scoped(prefix="rpt_1/attempt_01")

    ref_a = store.put_text(name="a.txt", content="hello")
    ref_b = store.put_bytes(name="b.bin", content=b"\x00\x01")
    ref_c = store.put_json(name="c.json", payload={"b": 2, "a": 1})

    assert ref_a.ref == "rpt_1/attempt_01/a.txt"
    assert ref_b.ref == "rpt_1/attempt_01/b.bin"
    assert ref_c.ref == "rpt_1/attempt_01/c.json"

    assert (tmp_path / "rpt_1" / "attempt_01" / "a.txt").read_text(encoding="utf-8") == "hello"
    assert (tmp_path / "rpt_1" / "attempt_01" / "b.bin").read_bytes() == b"\x00\x01"
    assert (tmp_path / "rpt_1" / "attempt_01" / "c.json").exists()

