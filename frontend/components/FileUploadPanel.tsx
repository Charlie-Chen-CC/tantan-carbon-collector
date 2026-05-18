'use client';

import React, { useState } from 'react';
import { Upload, Alert, Button, Space, message } from 'antd';
import {
  CheckCircleOutlined,
  LoadingOutlined,
  CloseCircleOutlined,
  FileOutlined,
  DeleteOutlined,
  UploadOutlined
} from '@ant-design/icons';

interface UploadFile {
  id: string;
  name: string;
  size: number;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  progress: number;
  error?: string;
  extractedData?: any;
}

interface FileUploadPanelProps {
  sessionId: string;
  section: number;
  onDataExtracted: (data: any) => void;
}

export default function FileUploadPanel({
  sessionId,
  section,
  onDataExtracted
}: FileUploadPanelProps) {
  const [files, setFiles] = useState<UploadFile[]>([]);

  const handleUpload = async (file: File) => {
    const fileId = Math.random().toString(36).substr(2, 9);

    // 添加到列表
    setFiles(prev => [...prev, {
      id: fileId,
      name: file.name,
      size: file.size,
      status: 'uploading',
      progress: 0
    }]);

    // 调用提取API
    const formData = new FormData();
    formData.append('file', file);

    setFiles(prev => prev.map(f =>
      f.id === fileId ? { ...f, status: 'processing', progress: 10 } : f
    ));

    try {
      const response = await fetch(
        `/api/extract/${sessionId}/section/${section}`,
        {
          method: 'POST',
          body: formData
        }
      );

      const result = await response.json();

      setFiles(prev => prev.map(f =>
        f.id === fileId ? {
          ...f,
          status: result.success ? 'completed' : 'failed',
          progress: 100,
          error: result.error,
          extractedData: result.filled_data
        } : f
      ));

      if (result.success && result.filled_data) {
        onDataExtracted(result.filled_data);
        message.success(`文件 "${file.name}" 提取完成`);
      } else if (result.error) {
        message.error(`文件 "${file.name}" 提取失败: ${result.error}`);
      }
    } catch (err: any) {
      setFiles(prev => prev.map(f =>
        f.id === fileId ? {
          ...f,
          status: 'failed',
          error: err.message
        } : f
      ));
      message.error(`文件 "${file.name}" 上传失败`);
    }

    return false; // 阻止默认上传
  };

  const removeFile = (fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'failed': return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'processing': return <LoadingOutlined />;
      default: return <FileOutlined />;
    }
  };

  const completedCount = files.filter(f => f.status === 'completed').length;
  const failedCount = files.filter(f => f.status === 'failed').length;

  return (
    <div style={{ marginTop: 24 }}>
      <Upload
        multiple
        beforeUpload={handleUpload}
        showUploadList={false}
        accept=".pdf,.doc,.docx,.xlsx,.xls,.png,.jpg,.jpeg,.md,.ppt,.pptx"
      >
        <Button icon={<UploadOutlined />}>批量上传证明文件</Button>
      </Upload>

      {files.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Alert
            message={
              <Space>
                <span>已上传 {files.length} 个文件</span>
                {completedCount > 0 && <span style={{ color: '#52c41a' }}>• {completedCount} 成功</span>}
                {failedCount > 0 && <span style={{ color: '#ff4d4f' }}>• {failedCount} 失败</span>}
              </Space>
            }
            type={failedCount > 0 ? 'warning' : 'info'}
            showIcon
          />

          <div style={{ marginTop: 12, maxHeight: 300, overflowY: 'auto' }}>
            {files.map(file => (
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
                  background: file.status === 'failed' ? '#fff2f0' : '#fafafa'
                }}
              >
                <Space>
                  {getStatusIcon(file.status)}
                  <span style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {file.name}
                  </span>
                  {file.status === 'processing' && (
                    <span style={{ color: '#999' }}>处理中...</span>
                  )}
                  {file.error && (
                    <span style={{ color: '#ff4d4f', fontSize: 12 }}>{file.error}</span>
                  )}
                </Space>

                {file.status !== 'processing' && (
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => removeFile(file.id)}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}