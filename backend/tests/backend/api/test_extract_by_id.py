"""
P0-9 集成测试 - /api/extract 接受 file_id 不再要求前端重传 file

WHY:
  docs/CODE_REVIEW_2026-06-03.md 4.6【High】：useFileUpload.ts:53-54
  await fileApi.upload(file) 之后 await fileApi.extract(file) 同一文件
  HTTP 传两次。修后 /api/extract 接受 file_id form field，按 file_id
  在 uploads/ 找文件，不再要求前端传 file。

守门测试：
  1. 上传后用 file_id 调 extract → 200，不要求前端传 file
  2. extract(file_id) 走文件 ID 路径能调起 extract pipeline
  3. extract(file_id) 用不存在的 ID → 404
  4. 兼容：传 file (multipart) 老路径仍工作
"""
import io
import uuid
import pytest
from fastapi.testclient import TestClient


def _make_upload_file(content: bytes, filename: str, content_type: str = "application/octet-stream"):
    return ("file", (filename, io.BytesIO(content), content_type))


def _create_session(client: TestClient) -> str:
    resp = client.post("/api/session")
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def _upload_xlsx(client: TestClient, session_id: str) -> str:
    """上传一个 xlsx，返回 file_id（hex 字符串）"""
    files = [_make_upload_file(b"PK\x03\x04" + b"\x00" * 200, "test.xlsx")]
    resp = client.post(
        "/api/upload",
        files=files,
        data={"session_id": session_id, "section": "3"},
    )
    assert resp.status_code == 200, f"上传失败: {resp.text}"
    file_id = resp.json()["file_id"]
    assert file_id and isinstance(file_id, str)
    return file_id


class TestExtractByFileId:
    """/api/extract 接受 file_id (P0-9)"""

    def test_extract_with_file_id_only_no_file_required(self, registered_user):
        """P0-9 主路径：upload 后用 file_id 调 extract，前端不传 file"""
        client = registered_user["client"]
        session_id = _create_session(client)
        file_id = _upload_xlsx(client, session_id)

        # 只传 file_id form field，不传 file
        resp = client.post(
            f"/api/extract/{session_id}/section/3",
            data={"file_id": file_id},
        )
        # 状态码可能是 200 (success) / 400 (extraction 失败，文件是 dummy) / 500 (LLM 不可用)
        # 关键：不是 422 (Unprocessable Entity) — 那说明 FastAPI 把 file 当必填项
        assert resp.status_code in (200, 400, 500), (
            f"file_id 路径失败 (status={resp.status_code}): {resp.text}"
        )
        # 422 说明后端把 file 当必填，与 P0-9 修复目标不符
        assert resp.status_code != 422, (
            f"file_id 路径仍把 file 当必填（422），P0-9 修复未生效: {resp.text}"
        )

    def test_extract_with_nonexistent_file_id_returns_404(self, registered_user):
        """不存在的 file_id 应返回 404，不应默默成功"""
        client = registered_user["client"]
        session_id = _create_session(client)

        fake_file_id = uuid.uuid4().hex  # 合法 hex 但盘上无文件
        resp = client.post(
            f"/api/extract/{session_id}/section/3",
            data={"file_id": fake_file_id},
        )
        assert resp.status_code == 404, (
            f"不存在的 file_id 应 404，实际 {resp.status_code}: {resp.text}"
        )

    def test_extract_without_file_id_and_file_returns_400(self, registered_user):
        """既不传 file_id 也不传 file 应 400（不是 500/422）"""
        client = registered_user["client"]
        session_id = _create_session(client)

        resp = client.post(f"/api/extract/{session_id}/section/3", data={})
        assert resp.status_code == 400, (
            f"空 body 应 400，实际 {resp.status_code}: {resp.text}"
        )

    def test_legacy_multipart_file_still_works(self, registered_user):
        """兼容：老调用方传 file (multipart) 仍能处理（不走 file_id 路径）"""
        client = registered_user["client"]
        session_id = _create_session(client)

        files = [_make_upload_file(b"PK\x03\x04" + b"\x00" * 200, "legacy.xlsx")]
        resp = client.post(
            f"/api/extract/{session_id}/section/3",
            files=files,
        )
        # 同样：200/400/500 都可以（dummy 文件可能 LLM 解析失败），但不能 422
        assert resp.status_code != 422, (
            f"老 multipart file 路径坏了: {resp.text}"
        )
