'use client';

/**
 * 侧边栏 - 步骤进度 + 折叠
 *
 * 包含：
 *   - Logo 区
 *   - 9 个 section 步骤节点
 *   - 当前 section 高亮 + 已完成打勾
 */
import { Layout } from 'antd';

const { Sider } = Layout;
import { RobotOutlined } from '@ant-design/icons';
import { SECTION_NAMES } from '../config/sectionConfig';
import styles from '../app/dashboard/page.module.css';

export interface FormSidebarProps {
  collapsed: boolean;
  currentSection: number;
  progress: Record<string, string>;
  onToggleCollapse: () => void;
  onSectionChange: (section: number) => void;
}

const statusBadgeClass = (status: string, isActive: boolean, isCompleted: boolean) => {
  if (isActive) return styles.stepItemActive;
  if (isCompleted) return styles.stepItemCompleted;
  return '';
};

const stepNodeClass = (isActive: boolean, isCompleted: boolean) => {
  if (isActive) return styles.stepNodeActive;
  if (isCompleted) return styles.stepNodeCompleted;
  return styles.stepNodeDefault;
};

export default function FormSidebar({
  collapsed,
  currentSection,
  progress,
  onSectionChange,
}: FormSidebarProps) {
  return (
    <Sider
      trigger={null}
      collapsible
      collapsed={collapsed}
      width={280}
      className={`${styles.sider} ${collapsed ? styles.siderCollapsed : ''}`}
    >
      <div className={styles.siderHeader}>
        <div className={styles.siderLogo}>
          <div className={styles.siderLogoIcon}>
            <RobotOutlined />
          </div>
          {!collapsed && (
            <div className={styles.siderLogoText}>
              <span className={styles.siderLogoTitle}>碳管师收资</span>
              <span className={styles.siderLogoSubtitle}>CARBON DATA</span>
            </div>
          )}
        </div>
      </div>

      {!collapsed && (
        <div className={styles.stepsContainer}>
          <div className={styles.stepsTitle}>填表进度</div>
          <div className={styles.steps}>
            {SECTION_NAMES.slice(1).map((name, idx) => {
              const section = idx + 1;
              const status = progress?.[String(section)] || 'not_started';
              const isActive = currentSection === section;
              const isCompleted = status === 'completed';

              return (
                <div
                  key={section}
                  className={`${styles.stepItem} ${statusBadgeClass(status, isActive, isCompleted)}`}
                  onClick={() => onSectionChange(section)}
                >
                  <div className={`${styles.stepNode} ${stepNodeClass(isActive, isCompleted)}`}>
                    {isCompleted ? '✓' : section}
                  </div>
                  <div className={styles.stepContent}>
                    <div className={styles.stepName}>{name}</div>
                    <div className={styles.stepMeta}>
                      {isCompleted ? '已完成' : isActive ? '进行中' : '未开始'}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Sider>
  );
}
