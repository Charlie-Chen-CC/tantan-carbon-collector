"""文件上传验证 - python-magic 真实 MIME 探测

被 files_router.upload_file 调用
"""
import os
import uuid
from typing import Tuple, Dict

import magic
from fastapi import HTTPException, UploadFile


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

ALLOWED_EXTENSIONS = {
    '.xlsx', '.xls', '.pdf', '.docx', '.doc',
    '.pptx', '.md', '.png', '.jpg', '.jpeg',
}

# 扩展名 -> 真实 MIME 类型白名单
# xlsx/docx/pptx 内部是 ZIP，python-magic 会返回 application/zip，因此需要双白名单
EXT_TO_MIMES: Dict[str, frozenset] = {
    '.xlsx': frozenset({
        'application/zip',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }),
    '.xls': frozenset({
        'application/vnd.ms-excel',
        'application/x-msexcel',
        'application/CDFV2',  # OLE2 复合文档（python-magic Windows 平台识别名）
    }),
    '.pdf': frozenset({'application/pdf'}),
    '.docx': frozenset({
        'application/zip',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }),
    '.doc': frozenset({
        'application/msword',
        'application/x-msdownload',
        'application/CDFV2',
    }),
    '.pptx': frozenset({
        'application/zip',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    }),
    '.md': frozenset({'text/plain', 'text/markdown', 'text/x-markdown', 'application/octet-stream'}),
    '.png': frozenset({'image/png'}),
    '.jpg': frozenset({'image/jpeg'}),
    '.jpeg': frozenset({'image/jpeg'}),
}


def validate_file(file: UploadFile) -> Tuple[str, str]:
    """真实探测文件类型，返回 (扩展名, 安全文件名)

    流程：
    1. 扩展名白名单
    2. 读前 2KB 用 python-magic 探测真实 MIME
    3. 扩展名对应的 MIME 白名单必须包含真实 MIME
    4. 用 uuid4 重写文件名（防路径遍历 + 防止泄露原始名）
    """
    _, ext = os.path.splitext(file.filename or '')
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，仅支持 xlsx/xls/pdf/docx/doc/pptx/md/png/jpg/jpeg"
        )

    try:
        head = file.file.read(2048)
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法读取文件内容: {e}") from e

    if not head:
        raise HTTPException(status_code=400, detail="空文件")

    detected_mime = magic.from_buffer(head, mime=True)
    allowed = EXT_TO_MIMES[ext]
    if detected_mime not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"文件内容类型 {detected_mime} 与扩展名 {ext} 不匹配"
        )

    safe_filename = f"{uuid.uuid4().hex}{ext}"
    return ext, safe_filename
