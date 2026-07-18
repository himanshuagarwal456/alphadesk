"""Phase 7 private research upload, isolation, and export filtering."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
from tradingagents.research.ingest import UploadValidationError, validate_and_extract


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHADESK_OBJECT_STORE_DIR", str(tmp_path / "objects"))
    app = create_app(database_url=f"sqlite:///{tmp_path / 'p7.db'}")
    return TestClient(app)


def _headers(workspace: str) -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


@pytest.mark.server
def test_upload_search_and_workspace_isolation(client: TestClient) -> None:
    content = b"# Private memo\nRevenue beat expectations for ACME.\n"
    upload = client.post(
        "/v1/research/documents",
        headers=_headers("ws_a"),
        files={"file": ("memo.md", content, "text/markdown")},
        data={"title": "ACME memo", "symbols": "ACME", "themes": "earnings"},
    )
    assert upload.status_code == 201, upload.text
    doc = upload.json()
    assert doc["ownership"] == "private"
    assert "Revenue beat" in doc["extracted_text"]
    assert doc["size_bytes"] == len(content)
    assert doc["evidence_id"]
    assert "ACME" in doc["symbols"]

    listed = client.get("/v1/research/documents", headers=_headers("ws_a"))
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    isolated = client.get("/v1/research/documents", headers=_headers("ws_b"))
    assert isolated.status_code == 200
    assert isolated.json() == []

    missing = client.get(
        f"/v1/research/documents/{doc['id']}", headers=_headers("ws_b")
    )
    assert missing.status_code == 404

    hits = client.get(
        "/v1/research/search",
        headers=_headers("ws_a"),
        params={"q": "ACME"},
    )
    assert hits.status_code == 200
    assert len(hits.json()) == 1
    assert hits.json()[0]["document"]["id"] == doc["id"]

    other_hits = client.get(
        "/v1/research/search",
        headers=_headers("ws_b"),
        params={"q": "ACME"},
    )
    assert other_hits.json() == []

    text = client.get(
        f"/v1/research/documents/{doc['id']}/text",
        headers=_headers("ws_a"),
    )
    assert text.status_code == 200
    assert "Revenue beat" in text.json()["extracted_text"]


@pytest.mark.server
def test_soft_delete_and_export_filter(client: TestClient) -> None:
    upload = client.post(
        "/v1/research/documents",
        headers=_headers("ws_res"),
        files={"file": ("notes.txt", b"confidential thesis notes", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    doc = upload.json()
    evidence_id = doc["evidence_id"]

    deleted = client.delete(
        f"/v1/research/documents/{doc['id']}",
        headers=_headers("ws_res"),
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    listed = client.get("/v1/research/documents", headers=_headers("ws_res"))
    assert listed.json() == []

    # Public exports exclude private evidence by default.
    filtered = client.post(
        "/v1/research/exports/filter",
        headers=_headers("ws_res"),
        json={"include_private": False, "evidence_ids": [evidence_id, "ev_public"]},
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert "ev_public" in body["evidence_ids"]
    assert evidence_id in body["excluded_private"]


@pytest.mark.server
def test_reject_oversized_and_executable(client: TestClient) -> None:
    huge = b"x" * (6 * 1024 * 1024)
    too_big = client.post(
        "/v1/research/documents",
        headers=_headers("ws_guard"),
        files={"file": ("big.txt", huge, "text/plain")},
    )
    assert too_big.status_code == 400

    exe = client.post(
        "/v1/research/documents",
        headers=_headers("ws_guard"),
        files={
            "file": (
                "bad.exe",
                b"MZ\x90\x00not an exe payload",
                "application/octet-stream",
            )
        },
    )
    assert exe.status_code == 400


def test_ingest_helpers_unit() -> None:
    extracted = validate_and_extract(filename="note.md", data=b"# hello\nworld")
    assert extracted.kind.value == "markdown"
    assert "hello" in extracted.extracted_text
    with pytest.raises(UploadValidationError):
        validate_and_extract(filename="x.exe", data=b"abc")
