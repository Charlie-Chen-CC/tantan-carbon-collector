"""
API路由测试 - 验证核心API端点
"""
import io
import pytest
from tantan.backend.api.validation import validate_file
from tantan.backend.api.routes import api_router
from fastapi import HTTPException


class TestFileValidation:
    """测试文件验证功能 (S1: 真实 MIME 探测)"""

    # 真实文件字节签名（python-magic 用这些识别真实类型）
    # OLE2 (.xls/.doc) 需 512 字节才会被识别为 application/CDFV2
    _OLE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * (512 - 8)
    _ZIP = b'PK\x03\x04' + b'\x00' * 200
    _PNG = bytes.fromhex('89504E470D0A1A0A0000000D49484452') + b'\x00' * 100
    _JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 200
    REAL_FILE_BYTES = {
        '.xlsx': _ZIP,
        '.xls':  _OLE,
        '.pdf':  b'%PDF-1.4\n' + b'\x00' * 200,
        '.docx': _ZIP,
        '.doc':  _OLE,
        '.pptx': _ZIP,
        '.md':   b'# Hello\nworld\n',
        '.png':  _PNG,
        '.jpg':  _JPG,
        '.jpeg': _JPG,
    }

    def _make_mock(self, filename: str, content: bytes) -> object:
        """构造一个支持 .file.read/.file.seek 的 Mock UploadFile"""
        class MockFile:
            pass
        m = MockFile()
        m.filename = filename
        m.content_type = 'application/octet-stream'
        # SpooledTemporaryFile 兼容接口：read/seek
        m.file = io.BytesIO(content)
        return m

    def test_validate_allowed_extensions(self):
        """所有白名单扩展名都应通过验证"""
        allowed = ['.xlsx', '.xls', '.pdf', '.docx', '.doc', '.pptx', '.md', '.png', '.jpg', '.jpeg']

        for ext in allowed:
            mock = self._make_mock(f'test{ext}', self.REAL_FILE_BYTES[ext])
            ext_returned, safe_name = validate_file(mock)
            assert ext_returned == ext
            assert safe_name.endswith(ext)
            assert len(safe_name) == len(ext) + 32  # uuid4().hex 长度

    def test_validate_disallowed_extension(self):
        """不支持的扩展名应被拒绝"""
        mock = self._make_mock('test.exe', b'MZ\x90\x00' + b'\x00' * 200)

        with pytest.raises(HTTPException) as exc_info:
            validate_file(mock)
        assert exc_info.value.status_code == 400
        assert '不支持的文件类型' in str(exc_info.value.detail)

    def test_validate_uppercase_extension(self):
        """大写扩展名应被规范化为小写"""
        mock = self._make_mock('test.XLSX', self.REAL_FILE_BYTES['.xlsx'])
        ext, safe_name = validate_file(mock)
        assert ext == '.xlsx'

    def test_validate_content_mismatch(self):
        """扩展名与内容不匹配应被拒绝（如 xlsx 但内容是 PDF）"""
        mock = self._make_mock('evil.xlsx', b'%PDF-1.4 fake content')
        with pytest.raises(HTTPException) as exc_info:
            validate_file(mock)
        assert exc_info.value.status_code == 400
        assert '不匹配' in str(exc_info.value.detail)

    def test_validate_empty_file(self):
        """空文件应被拒绝"""
        mock = self._make_mock('empty.xlsx', b'')
        with pytest.raises(HTTPException) as exc_info:
            validate_file(mock)
        assert exc_info.value.status_code == 400

    def test_validate_executable_rejected(self):
        """PE 可执行文件伪装为 xlsx 应被拒绝"""
        mock = self._make_mock('malware.xlsx', b'MZ\x90\x00' + b'\x00' * 200)
        with pytest.raises(HTTPException) as exc_info:
            validate_file(mock)
        assert exc_info.value.status_code == 400


class TestRouterSetup:
    """测试路由配置"""

    def test_api_router_aggregated(self):
        """验证 api_router 已聚合 7 个子 router"""
        assert api_router is not None
        # 收集所有子路由的端点路径
        all_paths = []
        for sub in api_router.routes:
            if hasattr(sub, 'routes'):
                all_paths.extend(r.path for r in sub.routes)
            elif hasattr(sub, 'path'):
                all_paths.append(sub.path)
        # 关键端点必须存在
        assert any('session' in p for p in all_paths)
        assert any('upload' in p for p in all_paths)
        assert any('extract' in p for p in all_paths)
        assert any('form' in p for p in all_paths)
        assert any('chat' in p for p in all_paths)
        assert any('history' in p for p in all_paths)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])