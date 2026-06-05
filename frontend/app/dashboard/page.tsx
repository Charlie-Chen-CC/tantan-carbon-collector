'use client';

/**
 * Dashboard - 主页面
 *
 * Phase 3.4 重构后：
 *   - 业务逻辑下沉到 hooks（useFormState / useFileUpload / useAIChat）
 *   - 视图下沉到 4 个组件（FormSidebar / FormSection / FloatingAI / FileUploadPanel）
 *   - 本文件只负责组合 + 状态编排（< 250 行）
 */
import { useState, useEffect } from 'react';
import { Layout, Form, Typography, Badge, message, Modal } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  CheckCircleOutlined,
  QuestionCircleOutlined,
  FileExcelOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../store/authStore';
import { useFormState } from '../../hooks/useFormState';
import FormSidebar from '../../components/FormSidebar';
import FormSection from '../../components/FormSection';
import FloatingAI from '../../components/FloatingAI';
import FileUploadPanel from '../../components/FileUploadPanel';
import { SECTION_NAMES, SECTION_FIELDS } from '../../config/sectionConfig';
import styles from './page.module.css';

const { Header, Content } = Layout;
const { Title } = Typography;
const { confirm } = Modal;

export default function DashboardPage() {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [form] = Form.useForm();
  const watchedValues = Form.useWatch([], form);

  // P0-10 修复：useFormState 接受 enabled，等 auth check 完成且 user 非空才创建
  // session。修前 useFormState 默认 enabled 与 providers.tsx initAuthEffects 同帧赛跑。
  const { session, switchSection, confirmSection } = useFormState(!!user);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/login');
    }
  }, [isLoading, user, router]);

  if (isLoading || !user || !session) {
    return null;
  }

  const currentSection = session.current_section;
  const fields = SECTION_FIELDS[currentSection] || [];
  const status = session.progress?.[String(currentSection)] || 'not_started';

  // 提取数据写入表单（FileUploadPanel / FormSection 共用）
  const fillFormFromExtracted = (data: Record<string, any>) => {
    Object.entries(data).forEach(([k, v]) => form.setFieldValue(k, v));
  };

  const handleConfirm = async () => {
    const values = form.getFieldsValue();
    try {
      await confirmSection(values);
    } catch {
      message.error('确认失败');
    }
  };

  const handleLogout = () => {
    confirm({
      title: '确认登出',
      content: '确定要退出登录吗？',
      onOk: async () => {
        await logout();
        router.push('/login');
      },
    });
  };

  return (
    <div className={styles.dashboardContainer}>
      <FormSidebar
        collapsed={collapsed}
        currentSection={currentSection}
        progress={session.progress || {}}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        onSectionChange={switchSection}
      />

      <Layout className={styles.mainLayout}>
        <Header className={styles.header}>
          <div className={styles.headerLeft}>
            <div className={styles.headerToggle} onClick={() => setCollapsed(!collapsed)}>
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </div>
            <h1 className={styles.headerTitle}>碳排放资料收集系统</h1>
          </div>
          <div className={styles.headerRight}>
            <div className={styles.headerUser}>
              <div className={styles.headerAvatar}>{user.username.charAt(0).toUpperCase()}</div>
              <span className={styles.headerUsername}>{user.username}</span>
            </div>
            <div className={styles.headerLogout} onClick={handleLogout}>
              <LogoutOutlined />
            </div>
          </div>
        </Header>

        <Content className={styles.content}>
          <div className={styles.contentCard}>
            <div className={styles.cardHeader}>
              <div className={styles.cardTitle}>
                <div className={styles.cardTitleIcon}>
                  <FileTextOutlined />
                </div>
                <div>
                  <Title level={4} className={styles.cardTitleText}>
                    第{currentSection}部分：{SECTION_NAMES[currentSection] || '未知部分'}
                  </Title>
                  <div className={styles.cardSubtitle}>请填写以下信息，确保数据准确完整</div>
                </div>
              </div>
              <div
                className={`${styles.cardStatus} ${
                  status === 'completed'
                    ? styles.cardStatusCompleted
                    : status === 'in_progress'
                      ? styles.cardStatusInProgress
                      : styles.cardStatusNotStarted
                }`}
              >
                <Badge
                  status={
                    status === 'completed'
                      ? 'success'
                      : status === 'in_progress'
                        ? 'processing'
                        : 'default'
                  }
                />
                {status === 'completed' ? '已完成' : status === 'in_progress' ? '进行中' : '未开始'}
              </div>
            </div>

            <div className={styles.cardBody}>
              <Form form={form} layout="vertical" key={`form-${currentSection}`}>
                <FormSection
                  fields={fields}
                  watchedValues={watchedValues || {}}
                  onFileUpload={fillFormFromExtracted}
                />
              </Form>

              <div className={styles.buttonGroup}>
                <button className={styles.buttonPrimary} onClick={handleConfirm}>
                  <CheckCircleOutlined />
                  确认完成
                </button>
                <button className={styles.buttonSecondary} onClick={() => setAiOpen(true)}>
                  <QuestionCircleOutlined />
                  碳排放助手
                </button>
              </div>

              <div className={styles.uploadSection}>
                <div className={styles.uploadHeader}>
                  <div className={styles.uploadTitle}>
                    <FileExcelOutlined />
                    证明文件上传
                  </div>
                </div>
                <div className={styles.uploadHint}>支持 .xlsx/.xls/.pdf 格式，可上传多个文件</div>
              </div>

              <FileUploadPanel
                sessionId={session.session_id}
                section={currentSection}
                onDataExtracted={fillFormFromExtracted}
              />
            </div>
          </div>
        </Content>
      </Layout>

      <FloatingAI
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        sessionId={session.session_id}
        currentSection={currentSection}
      />
    </div>
  );
}
