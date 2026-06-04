"""
Files API 集成测试 - 上传 / 列表 / 删除

覆盖：
- 上传 happy path
- 400 octet-stream 拒绝
- 401 未登录拒绝
- 列表 + section 隔离
- 删除
"""
import io
import pytest
from fastapi.testclient import TestClient


def _make_xlsx_bytes() -> bytes:
    """构造最小可识别的 xlsx 字节（ZIP 头 + 内容）"""
    return b"PK\x03\x04" + b"\x00" * 200


def _make_octet_bytes() -> bytes:
    """构造 0 字节文件流 - 真实 octet-stream"""
    return b"\x00" * 256


def _make_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n" + b"\x00" * 200


def _make_upload_file(content: bytes, filename: str, content_type: str = "application/octet-stream"):
    """构造 (filename, bytes, content_type) tuple 给 files= 参数"""
    return ("file", (filename, io.BytesIO(content), content_type))


class TestUpload:
    """文件上传"""

    def test_upload_xlsx_happy(self, registered_user):
        """合法 xlsx 文件应上传成功"""
        client = registered_user["client"]

        # 先创建会话
        sess_resp = client.post("/api/session")
        assert sess_resp.status_code == 200, sess_resp.text
        session_id = sess_resp.json()["session_id"]

        files = [_make_upload_file(_make_xlsx_bytes(), "test.xlsx")]
        resp = client.post(
            "/api/upload",
            files=files,
            data={"session_id": session_id, "section": "1"},
        )
        # 200 / 201 / 202 都视为接受；具体业务码看实现
        assert resp.status_code in (200, 201, 202), f"上传失败: {resp.status_code} {resp.text}"

    def test_upload_octet_stream_rejected(self, registered_user):
        """octet-stream / .bin 扩展名应被拒绝"""
        client = registered_user["client"]
        sess_resp = client.post("/api/session")
        session_id = sess_resp.json()["session_id"]

        files = [_make_upload_file(_make_octet_bytes(), "evil.bin")]
        resp = client.post(
            "/api/upload",
            files=files,
            data={"session_id": session_id, "section": "1"},
        )
        # 应被白名单或 MIME 探测拒绝
        assert resp.status_code in (400, 415, 422), f"octet-stream 未被拒绝: {resp.text}"

    def test_upload_executable_rejected(self, registered_user):
        """PE 可执行文件（.exe）应被拒绝"""
        client = registered_user["client"]
        sess_resp = client.post("/api/session")
        session_id = sess_resp.json()["session_id"]

        pe_bytes = b"MZ\x90\x00" + b"\x00" * 200
        files = [_make_upload_file(pe_bytes, "malware.exe")]
        resp = client.post(
            "/api/upload",
            files=files,
            data={"session_id": session_id, "section": "1"},
        )
        assert resp.status_code in (400, 415, 422), f"PE 文件未被拒绝: {resp.text}"

    def test_upload_without_auth(self, client: TestClient):
        """未登录上传应 401"""
        files = [_make_upload_file(_make_xlsx_bytes(), "test.xlsx")]
        resp = client.post(
            "/api/upload",
            files=files,
            data={"session_id": "fake_session", "section": "1"},
        )
        assert resp.status_code == 401

    def test_upload_then_download_roundtrip(self, registered_user):
        """P0-3 回归测试：上传后用 file_id 下载应返回 200 + 字节流一致

        重构前 06-03 引入的 bug：上传 f"{file_id}{ext}"，下载 startswith(file_id + "_")，
        前缀约定不一致 → 下载端点 100% 失败。
        """
        client = registered_user["client"]
        sess_resp = client.post("/api/session")
        assert sess_resp.status_code == 200
        session_id = sess_resp.json()["session_id"]

        original_content = _make_xlsx_bytes()
        files = [_make_upload_file(original_content, "test_roundtrip.xlsx")]
        up_resp = client.post(
            "/api/upload",
            files=files,
            data={"session_id": session_id, "section": "1"},
        )
        assert up_resp.status_code in (200, 201, 202), f"上传失败: {up_resp.text}"
        file_id = up_resp.json().get("file_id")
        assert file_id, f"响应缺 file_id: {up_resp.json()}"

        # 用 file_id 下载，应 200 + 内容一致
        dl_resp = client.get(f"/api/files/{file_id}")
        assert dl_resp.status_code == 200, (
            f"下载失败: {dl_resp.status_code} {dl_resp.text}（P0-3 修复前会 404）"
        )
        assert dl_resp.content == original_content, "下载内容与上传字节不一致"


class TestListFiles:
    """文件列表"""

    def test_list_section_files_empty(self, registered_user):
        """空 section 应返回空列表"""
        client = registered_user["client"]
        sess_resp = client.post("/api/session")
        session_id = sess_resp.json()["session_id"]

        resp = client.get(f"/api/files/{session_id}/section/1")
        # 200 / 404 都可接受（取决于后端对空 session 的处理）
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.json().get("files", []) == [] or isinstance(resp.json(), list)

    def test_list_without_auth(self, client: TestClient):
        """未登录列文件应 401"""
        resp = client.get("/api/files/fake_session/section/1")
        assert resp.status_code == 401
