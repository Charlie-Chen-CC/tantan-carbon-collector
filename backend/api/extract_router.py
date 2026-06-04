"""文件提取路由

- POST /api/extract/{session_id}/section/{section}        提取单个文件
- POST /api/extract/{session_id}/section/{section}/batch  批量提取（SSE）

SSE 协议说明（Phase 4 / P0-4 修复）：
  sse_starlette 1.8+ 的 EventSourceResponse 内部 AppStatus.should_exit_event
  类级 anyio.Event 单例，跨测试时会绑到已关闭的 event loop 抛 RuntimeError。
  这里直接 yield ServerSentEvent.encode() 返回的 bytes，配合 FastAPI
  StreamingResponse，行为等价但更稳（参考 chat_router.py chat_stream）。
"""
import asyncio
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sse_starlette.sse import ServerSentEvent

from tantan.backend.agents import FileExtractAgent, FormFillAgent
from tantan.backend.agents.file_processor import BatchFileProcessor
from tantan.backend.api.auth import get_current_user
from tantan.backend.models.database import User
from tantan.backend.state.database_manager import DatabaseStateManager
from tantan.backend.utils import log_exception
from tantan.backend.utils.exceptions import AppException, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extract", tags=["extract"])
state_manager = DatabaseStateManager()


@router.post("/{session_id}/section/{section}")
async def extract_section(
    session_id: str,
    section: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """提取文件中的部分数据"""
    try:
        if not 1 <= section <= 9:
            raise AppException(
                ErrorCode.SESSION_INVALID_SECTION,
                "无效的部分编号（1-9）",
                status_code=400,
            )

        session_data = state_manager.get_session(current_user.id, session_id)
        if not session_data:
            raise AppException(
                ErrorCode.SESSION_NOT_FOUND,
                "会话不存在",
                status_code=404,
            )

        content = await file.read()

        extractor = FileExtractAgent(section)
        result = extractor.process(content, filename=file.filename)

        if "error" in result:
            raise AppException(
                ErrorCode.EXTRACTION_FAILED,
                result["error"],
                status_code=400,
            )

        if result["status"] == "completed":
            filler = FormFillAgent(section)
            fill_result = filler.fill_form(result["data"])

            state_manager.save_form_data(current_user.id, session_id, section, fill_result.get("filled_data", {}))
            state_manager.update_progress(current_user.id, session_id, section, "awaiting_confirm")

            return {
                "success": True,
                "extracted_data": result["data"],
                "filled_data": fill_result.get("filled_data", {}),
                "errors": fill_result.get("errors", [])
            }

        raise AppException(
            ErrorCode.EXTRACTION_FAILED,
            "文件提取失败",
            status_code=400,
        )
    except AppException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": session_id, "section": section, "user_id": current_user.user_id, "action": "extract_section"})
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            "文件提取失败，请稍后重试",
            status_code=500,
            developer_message=str(e),
        )


@router.post("/{session_id}/section/{section}/batch")
async def extract_batch(
    session_id: str,
    section: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """批量提取文件数据（SSE 真实流式进度 / P0-4 修复）

    Event 序列（每个文件触发一次 progress 事件）：
        started (0/total)
        → progress (1/total) → ... → progress (total/total)
        → complete ({status, extracted, warnings, failed_files})
        或 catastrophic 异常时 → error ({error_code, user_message})

    实现关键（P0-4）：
      - **必须在路由函数体（yield 之前）await f.read()**：UploadFile 在请求
        body 关闭后再 read 会抛 "I/O operation on closed file"；StreamingResponse
        第一次迭代时请求已结束 → 文件必须在 yield 前读完。
      - **asyncio.Queue 桥接 callback 和 generator**：callback 是真 async callable，
        每处理完一个文件 put 一次 (processed, total)。generator 主循环用
        wait_for 拉 queue → yield SSE bytes。
      - 修前 bug：① progress_callback 死代码（占位注释）；
        ② yield ServerSentEvent 对象而非 .encode() bytes → StreamingResponse
        序列化抛 TypeError("encode() takes 1 positional argument but 2 were given")。
    """
    # 前置参数校验（在 yield 之前抛 AppException，正常 HTTP 4xx 响应）
    if not 1 <= section <= 9:
        raise AppException(
            ErrorCode.SESSION_INVALID_SECTION,
            "无效的部分编号（1-9）",
            status_code=400,
        )

    session_data = state_manager.get_session(current_user.id, session_id)
    if not session_data:
        raise AppException(
            ErrorCode.SESSION_NOT_FOUND,
            "会话不存在",
            status_code=404,
        )

    # 关键：必须在 yield 前读完所有 UploadFile（请求体关了就 read 不到）
    file_list = []
    for f in files:
        content = await f.read()
        file_list.append({
            "filename": f.filename,
            "content": content,
            "file_type": f.content_type,
        })

    total = len(file_list)

    async def event_generator():
        try:
            yield ServerSentEvent(
                event="progress",
                data=json.dumps({
                    "status": "started",
                    "total": total,
                    "processed": 0,
                }),
            ).encode()

            # P0-4 核心：用 asyncio.Queue 桥接 callback 和 SSE generator
            progress_queue: asyncio.Queue = asyncio.Queue()

            async def progress_callback(processed: int, total_count: int) -> None:
                await progress_queue.put((processed, total_count))

            processor = BatchFileProcessor(section=section)

            batch_task = asyncio.create_task(
                processor.process_batch(file_list, progress_callback=progress_callback)
            )

            # 主循环：等 batch 完成前持续 yield 进度事件
            while not batch_task.done():
                try:
                    processed, total_count = await asyncio.wait_for(
                        progress_queue.get(), timeout=0.5
                    )
                    yield ServerSentEvent(
                        event="progress",
                        data=json.dumps({
                            "status": "processing",
                            "processed": processed,
                            "total": total_count,
                        }),
                    ).encode()
                except asyncio.TimeoutError:
                    # 没新进度但 batch 还在跑，让出控制权继续等
                    continue

            result = await batch_task

            # 排空 queue（callback 可能在 batch_task done 之后还有 put）
            while not progress_queue.empty():
                try:
                    processed, total_count = progress_queue.get_nowait()
                    yield ServerSentEvent(
                        event="progress",
                        data=json.dumps({
                            "status": "processing",
                            "processed": processed,
                            "total": total_count,
                        }),
                    ).encode()
                except asyncio.QueueEmpty:
                    break

            yield ServerSentEvent(
                event="complete",
                data=json.dumps({
                    "status": result.status,
                    "extracted": result.extracted,
                    "warnings": result.warnings,
                    "failed_files": result.failed_files,
                }),
            ).encode()

        except Exception as e:
            # catastrophic 异常：单个文件失败已被 processor 捕获并写入 failed_files，
            # 到这里说明是 infrastructure 级别的错误（DB 挂、LLM 全挂等）。
            # SSE error 事件走 user_message，绝不暴露 str(e)
            log_exception(logger, e, {
                "session_id": session_id,
                "section": section,
                "user_id": current_user.user_id,
                "action": "extract_batch",
            })
            yield ServerSentEvent(
                event="error",
                data=json.dumps({
                    "error_code": ErrorCode.INTERNAL_ERROR.value,
                    "user_message": "批量提取失败，请稍后重试",
                }),
            ).encode()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
