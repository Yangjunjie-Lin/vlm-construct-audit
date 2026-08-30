from __future__ import annotations

from vlm_construct_audit.preregistration import frozen_snapshot
from vlm_construct_audit.preregistration.validation import (
    verify_p_mini_pilot_preregistration,
)


def test_successor_head_verifies_frozen_v1_snapshot() -> None:
    result = frozen_snapshot.verify_frozen_p_mini_pilot_preregistration_read_only()
    assert result["status"] == "PASS"
    assert result["peeled_commit"] != frozen_snapshot._git_bytes(
        "rev-parse", "HEAD"
    ).stdout.decode().strip()
    assert result["current_head_compared_to_snapshot"] is False
    assert result["current_worktree_compared_to_snapshot"] is False


def test_moved_v1_tag_target_fails(monkeypatch) -> None:
    monkeypatch.setattr(frozen_snapshot, "FROZEN_PREREGISTRATION_COMMIT", "0" * 40)
    result = frozen_snapshot.verify_frozen_p_mini_pilot_preregistration_read_only()
    assert result["status"] == "FAIL"
    assert any("tag target mismatch" in failure for failure in result["failures"])


def test_changed_frozen_file_hash_fails(monkeypatch) -> None:
    original = frozen_snapshot._snapshot_bytes

    def changed(path: str) -> bytes:
        content = original(path)
        if path == "configs/p_mini_pilot_models.yaml":
            return content + b"\n# modified after freeze\n"
        return content

    monkeypatch.setattr(frozen_snapshot, "_snapshot_bytes", changed)
    result = frozen_snapshot.verify_frozen_p_mini_pilot_preregistration_read_only()
    assert result["status"] == "FAIL"
    assert any("manifest hash mismatch" in failure for failure in result["failures"])


def test_original_verifier_keeps_exact_checkout_semantics() -> None:
    result = verify_p_mini_pilot_preregistration()
    assert result["status"] == "FAIL"
    assert result["tag_status"] == "FAIL"
    assert any("!= HEAD" in failure for failure in result["failures"])
