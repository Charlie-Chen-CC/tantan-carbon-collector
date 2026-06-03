'use client';

/**
 * 碳排放助手 - AI 悬浮窗
 *
 * 用 useAIChat hook 替代旧的本地 state + localStorage 手动同步，
 * 解决 3.5 消息重复插入 bug（hook 内部用 useRef activeConvIdRef 防止
 * 异步过程中 currentConvId 切换导致的重复追加）。
 *
 * 拖动用 useDragPosition hook：hasMoved 阈值区分点击 vs 拖动。
 *
 * 视觉：左对话列表 + 右聊天区，可最小化（close）。
 */
import { useEffect, useRef } from 'react';
import { RobotOutlined, PlusOutlined, SendOutlined, DeleteOutlined } from '@ant-design/icons';
import { useAIChat } from '../hooks/useAIChat';
import { useDragPosition } from '../hooks/useDragPosition';
import styles from '../app/dashboard/page.module.css';

export interface FloatingAIProps {
  open: boolean;
  onClose: () => void;
  sessionId: string | null;
  currentSection: number;
  /** 初始位置（来自悬浮球） */
  initialPos?: { x: number; y: number };
  /** 位置变化时通知父组件（用于持久化） */
  onPositionChange?: (pos: { x: number; y: number }) => void;
}

export default function FloatingAI({
  open,
  onClose,
  sessionId,
  currentSection,
  initialPos = { x: 24, y: 20 },
  onPositionChange,
}: FloatingAIProps) {
  const {
    conversations,
    currentConvId,
    currentMessages,
    isLoading,
    inputMessage,
    setInputMessage,
    setCurrentConvId,
    sendMessage,
    newConversation,
  } = useAIChat();

  const { position, dragHandlers, isDragging } = useDragPosition({
    initial: initialPos,
    threshold: 5,
  });

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentMessages]);

  useEffect(() => {
    onPositionChange?.(position);
  }, [position, onPositionChange]);

  if (!open) return null;

  const handleSend = () => {
    if (!sessionId) return;
    sendMessage(sessionId, currentSection);
  };

  return (
    <div
      className={styles.aiWindow}
      style={{
        right: position.x,
        bottom: position.y,
        cursor: isDragging ? 'grabbing' : 'default',
      }}
    >
      <div
        className={styles.aiHeader}
        {...dragHandlers}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <div className={styles.aiHeaderLeft}>
          <div className={styles.aiHeaderIcon}>
            <RobotOutlined />
          </div>
          <div>
            <div className={styles.aiHeaderTitle}>碳排放助手</div>
            <div className={styles.aiHeaderSubtitle}>专业碳排放数据咨询</div>
          </div>
        </div>
        <div
          className={styles.aiClose}
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
        >
          <DeleteOutlined />
        </div>
      </div>

      <div className={styles.aiBody}>
        <div className={styles.aiConversations}>
          <button className={styles.aiNewChat} onClick={newConversation}>
            <PlusOutlined /> 新对话
          </button>
          <div>
            {conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => setCurrentConvId(conv.id)}
                className={`${styles.aiConversationItem} ${
                  currentConvId === conv.id ? styles.aiConversationItemActive : ''
                }`}
              >
                {conv.title}
              </div>
            ))}
          </div>
        </div>

        <div className={styles.aiChatArea}>
          <div className={styles.aiMessages}>
            {currentMessages.length === 0 ? (
              <div className={styles.aiEmptyChat}>
                <RobotOutlined className={styles.aiEmptyIcon} />
                <div className={styles.aiEmptyTitle}>欢迎使用碳排放助手</div>
                <div className={styles.aiEmptyHint}>您可以咨询碳排放相关专业问题</div>
              </div>
            ) : (
              currentMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`${styles.aiMessage} ${
                    msg.role === 'user' ? styles.aiMessageUser : styles.aiMessageAssistant
                  }`}
                >
                  {msg.content}
                </div>
              ))
            )}
            {isLoading && <div className={styles.aiEmptyChat}>思考中...</div>}
            <div ref={chatEndRef} />
          </div>

          <div className={styles.aiInput}>
            <input
              type="text"
              className={styles.aiInputField}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="输入您的问题..."
            />
            <button
              className={styles.aiSendButton}
              onClick={handleSend}
              disabled={isLoading || !inputMessage.trim() || !sessionId}
            >
              <SendOutlined />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
