/**
 * 通用拖动定位 hook - 用于悬浮球和悬浮窗
 *
 * 返回：
 *   - position: {x, y} 当前位置
 *   - isDragging: 是否正在拖动
 *   - wasJustDragged: 本次按下是否触发了拖动（用于区分点击 vs 拖动）
 *   - dragHandlers: { onMouseDown } 绑定到拖动手柄
 *   - reset: 重置位置到初始值
 */
import { useEffect, useRef, useState, useCallback } from 'react';

export interface Position {
  x: number;
  y: number;
}

export interface UseDragPositionOptions {
  initial: Position;
  /** 触发拖动的最小位移（像素），用于区分点击 vs 拖动 */
  threshold?: number;
}

export interface UseDragPositionReturn {
  position: Position;
  isDragging: boolean;
  wasJustDragged: boolean;
  dragHandlers: { onMouseDown: (e: React.MouseEvent) => void };
  reset: (newPos?: Position) => void;
}

export const useDragPosition = (options: UseDragPositionOptions): UseDragPositionReturn => {
  const { initial, threshold = 5 } = options;
  const [position, setPosition] = useState<Position>(initial);
  const [isDragging, setIsDragging] = useState(false);
  const [wasJustDragged, setWasJustDragged] = useState(false);
  const startRef = useRef<{ mouseX: number; mouseY: number; posX: number; posY: number } | null>(
    null,
  );
  const hasMovedRef = useRef(false);

  useEffect(() => {
    if (!isDragging) return;
    const handleMove = (e: MouseEvent) => {
      if (!startRef.current) return;
      const dx = e.clientX - startRef.current.mouseX;
      const dy = e.clientY - startRef.current.mouseY;
      if (!hasMovedRef.current && Math.hypot(dx, dy) > threshold) {
        hasMovedRef.current = true;
      }
      if (hasMovedRef.current) {
        setPosition({
          x: startRef.current.posX + dx,
          y: startRef.current.posY + dy,
        });
      }
    };
    const handleUp = () => {
      if (hasMovedRef.current) {
        setWasJustDragged(true);
        // 短延迟后清 flag，避免影响下一次 onClick
        setTimeout(() => setWasJustDragged(false), 0);
      }
      setIsDragging(false);
      startRef.current = null;
    };
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
    return () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };
  }, [isDragging, threshold]);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      startRef.current = {
        mouseX: e.clientX,
        mouseY: e.clientY,
        posX: position.x,
        posY: position.y,
      };
      hasMovedRef.current = false;
      setIsDragging(true);
    },
    [position],
  );

  const reset = useCallback(
    (newPos?: Position) => {
      setPosition(newPos ?? initial);
    },
    [initial],
  );

  return {
    position,
    isDragging,
    wasJustDragged,
    dragHandlers: { onMouseDown },
    reset,
  };
};
