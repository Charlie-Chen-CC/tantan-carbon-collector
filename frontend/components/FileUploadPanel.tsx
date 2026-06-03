'use client';

/**
 * 文件上传面板 - 纯组件（受控 props）
 *
 * 重构要点：
 *   - 用 useFileUpload hook 替代手写 fetch + getAuthToken（已废弃）
 *   - 后端 httpOnly cookie 认证，前端无 token 操作
 *   - useRef uploadingRef 在 hook 内部防止重入上传（修复 3.7 重复上传）
 *   - 切换 section 时 hook 自动刷新文件列表
 *
 * props：
 *   - sessionId / section：当前会话与 section
 *   - onDataExtracted：extract 返回的 filled_data 透传给父组件
 */
import { Upload, Alert, Button, Space, Progress } from 'antd';
import {
  CheckCircleOutlined,
  LoadingOutlined,
  CloseCircleOutlined,
  FileOutlined,
  DeleteOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { useFileUpload } from '../hooks/useFileUpload';
import { SectionFile } from '../services/api';

type DisplayStatus = 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';

function toDisplayStatus(s: string): DisplayStatus {
  if (s === 'processed') return 'completed';
  if (s === 'uploading' || s === 'processing' || s === 'pending' || s === 'failed') {
    return s as DisplayStatus;
  }
  return 'completed';
}

export interface FileUploadPanelProps {
  sessionId: string;
  section: number;
  onDataExtracted: (data: Record<string, any>) => void;
}

export default function FileUploadPanel({
  sessionId,
  section,
  onDataExtracted,
}: FileUploadPanelProps) {
  const { files, isUploading, uploadAndExtract, deleteFile } = useFileUpload(sessionId, section);

  const handleBeforeUpload = async (file: File): Promise<boolean> => {
    const filledData = await uploadAndExtract(file);
    if (filledData) {
      onDataExtracted(filledData);
    }
    return false; // 阻止 antd Upload 默认行为
  };

  const handleRemove = async (file: SectionFile) => {
    await deleteFile(file.id);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'processing':
      case 'uploading':
        return <LoadingOutlined />;
      default:
        return <FileOutlined />;
    }
  };

  const completedCount = files.filter((f) => toDisplayStatus(f.status) === 'completed').length;
  const failedCount = files.filter((f) => toDisplayStatus(f.status) === 'failed').length;

  return (
    <div style={{ marginTop: 24 }}>
      <Upload
        multiple
        beforeUpload={handleBeforeUpload as any}
        showUploadList={false}
        accept=".pdf,.doc,.docx,.xlsx,.xls,.png,.jpg,.jpeg,.md,.ppt,.pptx"
      >
        <Button icon={<UploadOutlined />} loading={isUploading}>
          批量上传证明文件
        </Button>
      </Upload>

      {files.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Alert
            message={
              <Space>
                <span>已上传 {files.length} 个文件</span>
                {completedCount > 0 && (
                  <span style={{ color: '#52c41a' }}>• {completedCount} 成功</span>
                )}
                {failedCount > 0 && <span style={{ color: '#ff4d4f' }}>• {failedCount} 失败</span>}
              </Space>
            }
            type={failedCount > 0 ? 'warning' : 'info'}
            showIcon
          />

          <div style={{ marginTop: 12, maxHeight: 300, overflowY: 'auto' }}>
            {files.map((file) => {
              const status = toDisplayStatus(file.status);
              return (
                <div
                  key={file.id}
                  style={{
                    padding: '8px 12px',
                    marginBottom: 8,
                    border: '1px solid #f0f0f0',
                    borderRadius: 4,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: status === 'failed' ? '#fff2f0' : '#fafafa',
                  }}
                >
                  <Space>
                    {getStatusIcon(status)}
                    <span
                      style={{
                        maxWidth: 200,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {file.name}
                    </span>
                    {(status === 'processing' || status === 'uploading') && (
                      <Progress
                        percent={50}
                        size="small"
                        status="active"
                        style={{ marginLeft: 8, display: 'inline-block', width: 100 }}
                      />
                    )}
                  </Space>

                  {status !== 'processing' && status !== 'uploading' && (
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={() => handleRemove(file)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
