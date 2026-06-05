/**
 * 文件上传 hook - 修复 3.7 重复上传 bug
 *
 * 关键设计：
 *   - useRef uploadingRef 防止同一文件被并发上传
 *   - 每次切换 section 自动刷新文件列表
 *   - 上传完成后调 extract 端点，AI 填充返回 filled_data
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { fileApi, SectionFile } from '../services/api';

export interface UseFileUploadReturn {
  files: SectionFile[];
  isUploading: boolean;
  uploadAndExtract: (file: File) => Promise<Record<string, any> | null>;
  deleteFile: (fileId: number) => Promise<void>;
  refresh: () => Promise<void>;
}

export const useFileUpload = (sessionId: string | null, section: number): UseFileUploadReturn => {
  const [files, setFiles] = useState<SectionFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  // 关键：用 ref 而非 state 防止重入（state 更新异步，ref 立即生效）
  const uploadingRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!sessionId) {
      setFiles([]);
      return;
    }
    try {
      const resp = await fileApi.getSectionFiles(sessionId, section);
      setFiles(resp.data.files ?? []);
    } catch {
      setFiles([]);
    }
  }, [sessionId, section]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const uploadAndExtract = useCallback(
    async (file: File): Promise<Record<string, any> | null> => {
      if (!sessionId) return null;
      // ref 防重入：同步检查，避免 React state 异步更新导致的双重上传
      if (uploadingRef.current) {
        return null;
      }
      uploadingRef.current = true;
      setIsUploading(true);
      try {
        // P0-9 修复：先上传一次拿 file_id，extract 用 file_id 不再传 file
        // 修前：await upload() + await extract(file) → 同一文件 HTTP 传两次
        // 修后：await upload() 拿 file_id + await extract(fileId) → 1 次上传
        const uploadResp = await fileApi.upload(sessionId, section, file);
        const fileId = uploadResp.data?.file_id;
        if (!fileId) {
          throw new Error('upload 响应缺 file_id');
        }
        const extractResp = await fileApi.extract(sessionId, section, fileId);
        const data = extractResp.data;
        // 刷新文件列表（extract 不一定新增文件，但安全起见）
        await refresh();
        if (data?.success && data.filled_data) {
          return data.filled_data as Record<string, any>;
        }
        return null;
      } finally {
        uploadingRef.current = false;
        setIsUploading(false);
      }
    },
    [sessionId, section, refresh],
  );

  const deleteFile = useCallback(
    async (fileId: number) => {
      if (!sessionId) return;
      try {
        await fileApi.deleteFile(fileId);
        await refresh();
      } catch {
        // 静默失败，由 UI 反馈
      }
    },
    [sessionId, refresh],
  );

  return { files, isUploading, uploadAndExtract, deleteFile, refresh };
};
