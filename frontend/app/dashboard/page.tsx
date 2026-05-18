'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Layout, Menu, Form, Input, InputNumber, Select, Button, Upload, Table,
  Progress, Card, Typography, Badge, Dropdown, Avatar, Space, message,
  Modal, List, Typography as AntTypography, Tooltip, Tabs, Result, Spin
} from 'antd';
import {
  UserOutlined, LogoutOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
  FileTextOutlined, UploadOutlined, RobotOutlined, CheckCircleOutlined,
  ClockCircleOutlined, CloseCircleOutlined, PlusOutlined, DeleteOutlined,
  SendOutlined, LeftOutlined, RightOutlined, QuestionCircleOutlined
} from '@ant-design/icons';
import type { MenuProps, UploadProps, TableProps } from 'antd';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../store/authStore';
import { sessionApi, formApi, fileApi, chatApi, SessionData } from '../../services/api';
import FileUploadPanel from '../../components/FileUploadPanel';

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;
const { confirm } = Modal;

// ============ 类型定义 ============

type FieldType = 'text' | 'number' | 'select' | 'file' | 'multi-row';

interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  placeholder?: string;
  options?: string[];
  unit?: string;
  maxRows?: number;
  fields?: FieldDef[];
  fileAccept?: string;
  conditionField?: string;
  conditionValue?: string;
}

interface MultiRowEntry {
  id: string;
  [subKey: string]: string | number | File | null;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  timestamp?: string;
}

interface AIConversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
}

// ============ 常量配置 ============

const SECTION_NAMES = [
  '', '基本信息', '产品', '燃料使用', '电力、热力使用',
  '制冷剂使用', '其他散逸类排放', '三废处理', '原材料使用', '生产耗材'
];

const SECTION_FIELDS: { [section: number]: FieldDef[] } = {
  1: [
    { key: 'enterpriseName', label: '企业名称', type: 'text', placeholder: '请输入企业全称' },
    { key: 'industry', label: '所属行业', type: 'text', placeholder: '请输入所属行业' },
    { key: 'contact', label: '联系人', type: 'text', placeholder: '请输入联系人姓名' },
    { key: 'contactPhone', label: '联系方式', type: 'text', placeholder: '请输入联系电话' },
    { key: 'productionAddress', label: '生产地址', type: 'text', placeholder: '请输入生产地址' },
    { key: 'accountingYear', label: '核算年份', type: 'text', placeholder: '如：2024' },
    { key: 'isNaturalYear', label: '是否为自然年（1月1日-12月31日）', type: 'select', options: ['是', '否'] },
    { key: 'accountingPeriodNote', label: '核算周期说明', type: 'text', placeholder: '如：2024年1月1日至2024年6月30日', conditionField: 'isNaturalYear', conditionValue: '否' },
  ],
  2: [
    { key: 'targetProductName', label: 'PCF核算目标产品名称', type: 'text', placeholder: '请输入目标产品名称' },
    { key: 'isOnlyProduct', label: '是否为生产工厂唯一产品', type: 'select', options: ['是', '否'] },
    { key: 'otherProducts', label: '其他产品', type: 'multi-row', maxRows: 5, fields: [
      { key: 'name', label: '产品名称', type: 'text', placeholder: '产品名称' },
    ]},
    { key: 'isUniqueProductNote', label: '唯一产品超过5种的说明', type: 'text', placeholder: '如有超过5种其他产品，请在此说明' },
    { key: 'unit', label: '计量单位', type: 'select', options: ['按重量计量：t', '按体积计量：m³', '按面积计量：m²', '按长度计量：m', '按个数计量：只/个', '其他'] },
    { key: 'hasByProduct', label: '目标产品产线内是否有副产品', type: 'select', options: ['是', '否'] },
    { key: 'byProducts', label: '副产品', type: 'multi-row', maxRows: 5, fields: [
      { key: 'name', label: '副产品名称', type: 'text', placeholder: '副产品名称' },
    ]},
  ],
  3: [
    { key: 'boilerFuel', label: '生产用锅炉燃料', type: 'multi-row', maxRows: 1, fields: [
      { key: 'fuelType', label: '燃料类型', type: 'select', options: ['无', '液化天然气', '管道天然气', '压缩天然气', '液化石油气', '煤', '石油焦', '其他'] },
      { key: 'amount', label: '核算周期内使用量', type: 'number', placeholder: '0' },
      { key: 'unit', label: '单位', type: 'select', options: ['t', 'm³', 'kg', 'L'] },
      { key: 'measuredCalorific', label: '实测热值（如无则不填）', type: 'number', placeholder: '0' },
      { key: 'calorificUnit', label: '热值单位', type: 'select', options: ['MJ/kg', 'GJ/t', 'kJ/m³'] },
    ]},
    { key: 'wasteIncineratorFuel', label: '专用废气焚烧炉燃料', type: 'multi-row', maxRows: 1, fields: [
      { key: 'fuelType', label: '燃料类型', type: 'select', options: ['无', '液化天然气', '管道天然气', '压缩天然气', '液化石油气', '煤', '石油焦', '其他'] },
      { key: 'amount', label: '核算周期内使用量', type: 'number', placeholder: '0' },
      { key: 'unit', label: '单位', type: 'select', options: ['t', 'm³', 'kg', 'L'] },
    ]},
    { key: 'generatorFuel', label: '发电机燃料', type: 'multi-row', maxRows: 1, fields: [
      { key: 'fuelType', label: '燃料类型', type: 'select', options: ['无', '液化天然气', '管道天然气', '压缩天然气', '液化石油气', '煤', '石油焦', '柴油', '其他'] },
      { key: 'amount', label: '核算周期内使用量', type: 'number', placeholder: '0' },
      { key: 'unit', label: '单位', type: 'select', options: ['t', 'm³', 'kg', 'L'] },
    ]},
    { key: 'forkliftFuel', label: '厂内转运叉车燃料', type: 'multi-row', maxRows: 1, fields: [
      { key: 'fuelType', label: '燃料类型', type: 'select', options: ['无', '柴油叉车', '电叉车'] },
      { key: 'amount', label: '核算周期内使用量', type: 'number', placeholder: '0' },
      { key: 'unit', label: '单位', type: 'select', options: ['L', 'kg', 'kWh'] },
    ]},
  ],
  4: [
    { key: 'totalElectricity', label: '全厂用电总量(kWh)', type: 'number', placeholder: '0' },
    { key: 'productionElectricity', label: '生产用电总量(kWh)', type: 'number', placeholder: '0' },
    { key: 'officeElectricity', label: '行政办公用电量(kWh)', type: 'number', placeholder: '0' },
    { key: 'productLineElectricity', label: '目标产品产线用电量(kWh)', type: 'number', placeholder: '0' },
    { key: 'solarGeneration', label: '光伏发电量(kWh)', type: 'number', placeholder: '0' },
    { key: 'solarConfig', label: '光伏配置方式', type: 'select', options: ['无', '自建光伏-自用', '自建光伏-上网出售', '出租屋顶服务方投资-绿色权益归己方', '出租屋顶服务方投资-绿色权益归投资服务方', '出租屋顶服务方投资-绿色权益归属不明'] },
    { key: 'greenCertificate', label: '是否购买绿证', type: 'select', options: ['否', '是'] },
    { key: 'greenCertificateType', label: '绿证类型', type: 'select', options: ['无', '购买中国绿证GEC', '购买国外绿证IREC', '购买国外绿证TIGR', '其他'], conditionField: 'greenCertificate', conditionValue: '是' },
    { key: 'totalSteam', label: '全厂用蒸汽总量(t)', type: 'number', placeholder: '0' },
    { key: 'productionSteam', label: '生产用蒸汽总量(t)', type: 'number', placeholder: '0' },
  ],
  5: [
    { key: 'airConditioners', label: '空调制冷剂', type: 'multi-row', maxRows: 5, fields: [
      { key: 'equipmentName', label: '设备名称', type: 'text', placeholder: '如：办公区空调1' },
      { key: 'refrigerantNo', label: '制冷剂标号', type: 'select', options: ['R32', 'R410A', 'R134a', 'R22', 'R290', '其他'] },
      { key: 'fillAmount', label: '初始填充量累计(kg)', type: 'number', placeholder: '0' },
    ]},
    { key: 'freezers', label: '冷冻机制冷剂', type: 'multi-row', maxRows: 5, fields: [
      { key: 'equipmentName', label: '设备名称', type: 'text', placeholder: '如：冷库冷冻机1' },
      { key: 'refrigerantNo', label: '制冷剂标号', type: 'select', options: ['R32', 'R410A', 'R134a', 'R22', 'R290', '其他'] },
      { key: 'fillAmount', label: '初始填充量累计(kg)', type: 'number', placeholder: '0' },
    ]},
  ],
  6: [
    { key: 'co2Extinguisher', label: 'CO2灭火器填充总量(kg)', type: 'number', placeholder: '如：40只×5kg=200kg，填200' },
    { key: 'employeeHours', label: '核算期内员工总工时(小时/人/年)', type: 'number', placeholder: '20000' },
  ],
  7: [
    { key: 'wastewaterTreatment', label: '废水处理方式', type: 'select', options: ['厂内无废水处理设施', '厂内有废水处理设施-无厌氧工艺单元', '厂内有废水处理设施-有厌氧处理工艺单元'] },
    { key: 'wastewaterAmount', label: '废水处理量(m³)', type: 'number', placeholder: '0' },
    { key: 'hazardousWasteOutsourceIncineration', label: '危废委外焚烧量(t/年)', type: 'number', placeholder: '0' },
  ],
  8: [
    { key: 'processFlowDesc', label: 'PCF核算目标产品生产工艺流程文字描述', type: 'text', placeholder: '请描述生产工艺流程' },
    { key: 'rawMaterials', label: 'PCF核算目标产品耗用原材料', type: 'multi-row', maxRows: 10, fields: [
      { key: 'name', label: '原材料名称', type: 'text', placeholder: '如：硫酸' },
      { key: 'spec', label: '化学分子式/规格', type: 'text', placeholder: '如：20%硫酸' },
      { key: 'amount', label: '使用量', type: 'number', placeholder: '0' },
      { key: 'unit', label: '单位', type: 'select', options: ['kg', 't', 'm³', 'L'] },
    ]},
    { key: 'suppliers', label: 'PCF核算目标产品原材料上游供应商', type: 'multi-row', maxRows: 12, fields: [
      { key: 'name', label: '供应商名称', type: 'text', placeholder: '如：供应商A' },
      { key: 'materialCategory', label: '采购的原材料品类', type: 'text', placeholder: '如：硫酸' },
      { key: 'transportMode', label: '运输方式', type: 'select', options: ['公路运输', '铁路运输', '水路运输', '多式联运', '其他'] },
      { key: 'distance', label: '单程运距(km)', type: 'number', placeholder: '0' },
    ]},
  ],
  9: [
    { key: 'freshWaterCaliber', label: '新鲜水统计口径', type: 'select', options: ['全厂生产耗用量', '目标产品产线内容耗用量', '目标产品单耗'] },
    { key: 'freshWaterAmount', label: '新鲜水使用量(t)', type: 'number', placeholder: '0' },
    { key: 'nitrogenCaliber', label: '氮气统计口径', type: 'select', options: ['全厂生产耗用量', '目标产品产线内容耗用量', '目标产品单耗'] },
    { key: 'nitrogenAmount', label: '氮气使用量(m³)', type: 'number', placeholder: '0' },
  ],
};

// ============ 工具函数 ============

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

// ============ 多行表格组件 ============

interface MultiRowTableProps {
  field: FieldDef;
  entries: MultiRowEntry[];
  onChange: (key: string, entries: MultiRowEntry[]) => void;
}

function MultiRowTable({ field, entries, onChange }: MultiRowTableProps) {
  const handleAddRow = () => {
    if (field.maxRows !== -1 && entries.length >= field.maxRows!) return;
    const newEntry: MultiRowEntry = { id: generateId() };
    field.fields?.forEach(f => { newEntry[f.key] = ''; });
    onChange(field.key, [...entries, newEntry]);
  };

  const handleRemoveRow = (id: string) => {
    onChange(field.key, entries.filter(e => e.id !== id));
  };

  const handleSubFieldChange = (id: string, subKey: string, value: string) => {
    onChange(field.key, entries.map(e =>
      e.id === id ? { ...e, [subKey]: value } : e
    ));
  };

  const columns: TableProps<any>['columns'] = field.fields?.map(f => ({
    title: f.label,
    dataIndex: f.key,
    key: f.key,
    width: 180,
    render: (_: any, record: MultiRowEntry) => {
      if (f.type === 'select') {
        return (
          <Select
            value={String(record[f.key] || '')}
            onChange={val => handleSubFieldChange(record.id, f.key, val)}
            placeholder={f.placeholder}
            style={{ width: '100%' }}
          >
            {f.options?.map(opt => <Select.Option key={opt} value={opt}>{opt}</Select.Option>)}
          </Select>
        );
      }
      if (f.type === 'number') {
        return (
          <InputNumber
            value={Number(record[f.key]) || 0}
            onChange={val => handleSubFieldChange(record.id, f.key, String(val || ''))}
            placeholder={f.placeholder}
            style={{ width: '100%' }}
          />
        );
      }
      return (
        <Input
          value={String(record[f.key] || '')}
          onChange={e => handleSubFieldChange(record.id, f.key, e.target.value)}
          placeholder={f.placeholder}
        />
      );
    }
  })).concat([{
    title: '',
    dataIndex: 'action',
    key: 'action',
    width: 60,
    render: (_: any, record: MultiRowEntry) => (
      <Button type="text" danger icon={<DeleteOutlined />} onClick={() => handleRemoveRow(record.id)} />
    )
  }]) as TableProps<any>['columns'];

  return (
    <Card size="small" title={field.label} extra={
      <Space>
        <Text type="secondary">{entries.length}/{field.maxRows || '∞'}</Text>
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleAddRow}
          disabled={field.maxRows !== -1 && entries.length >= field.maxRows!}>
          添加
        </Button>
      </Space>
    }>
      {entries.length > 0 ? (
        <Table
          columns={columns}
          dataSource={entries}
          rowKey="id"
          size="small"
          pagination={false}
          scroll={{ x: 'max-content' }}
        />
      ) : (
        <div style={{ textAlign: 'center', padding: 24, color: '#999' }}>
          暂无数据，<Button type="link" onClick={handleAddRow}>点击添加</Button>
        </div>
      )}
    </Card>
  );
}

// ============ AI助手组件 ============

interface AIAssistantProps {
  open: boolean;
  onClose: () => void;
  sessionId: string | null;
  currentSection: number;
}

function AIAssistant({ open, onClose, sessionId, currentSection }: AIAssistantProps) {
  const [conversations, setConversations] = useState<AIConversation[]>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('ai_conversations');
      return saved ? JSON.parse(saved) : [];
    }
    return [];
  });
  const [currentConvId, setCurrentConvId] = useState<string | null>(null);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const currentConversation = conversations.find(c => c.id === currentConvId);
  const currentMessages = currentConversation?.messages || [];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentMessages]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('ai_conversations', JSON.stringify(conversations));
    }
  }, [conversations]);

  const handleNewConversation = () => {
    const newConv: AIConversation = {
      id: generateId(),
      title: '新对话',
      messages: [],
      createdAt: new Date().toISOString()
    };
    setConversations(prev => [newConv, ...prev]);
    setCurrentConvId(newConv.id);
    setInputMessage('');
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !sessionId) return;

    let convId = currentConvId;
    if (!convId) {
      const newConv: AIConversation = {
        id: generateId(),
        title: inputMessage.slice(0, 20),
        messages: [],
        createdAt: new Date().toISOString()
      };
      setConversations(prev => [newConv, ...prev]);
      convId = newConv.id;
      setCurrentConvId(convId);
    }

    const userMessage: ChatMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    setConversations(prev => prev.map(c =>
      c.id === convId ? { ...c, messages: [...c.messages, userMessage], title: inputMessage.slice(0, 20) || '新对话' } : c
    ));
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await chatApi.send(sessionId, inputMessage, { current_section: currentSection });
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.data.content,
        intent: response.data.intent,
        timestamp: new Date().toISOString()
      };
      setConversations(prev => prev.map(c =>
        c.id === convId ? { ...c, messages: [...c.messages, userMessage, assistantMessage] } : c
      ));
    } catch {
      message.error('发送消息失败');
    } finally {
      setIsLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div style={{
      position: 'fixed',
      right: 24,
      bottom: 24,
      width: 480,
      height: 560,
      background: '#fff',
      borderRadius: 8,
      boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 1000
    }}>
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: '8px 8px 0 0',
        color: '#fff'
      }}>
        <Space>
          <RobotOutlined />
          <span style={{ fontWeight: 500 }}>AI碳管师助手</span>
        </Space>
        <Button type="text" icon={<DeleteOutlined />} onClick={onClose} style={{ color: '#fff' }} />
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* 对话列表 */}
        <div style={{ width: 140, borderRight: '1px solid #f0f0f0', padding: 8 }}>
          <Button block onClick={handleNewConversation} icon={<PlusOutlined />} style={{ marginBottom: 8 }}>
            新建对话
          </Button>
          <div style={{ overflowY: 'auto', maxHeight: 'calc(100% - 48px)' }}>
            {conversations.map(conv => (
              <div
                key={conv.id}
                onClick={() => setCurrentConvId(conv.id)}
                style={{
                  padding: '8px 12px',
                  marginBottom: 4,
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontSize: 12,
                  background: currentConvId === conv.id ? '#f0f0f0' : 'transparent',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}
              >
                {conv.title}
              </div>
            ))}
          </div>
        </div>

        {/* 聊天区域 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
            {currentMessages.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#999', marginTop: 100 }}>
                <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                <p>欢迎使用AI碳管师助手</p>
                <p style={{ fontSize: 12 }}>您可以咨询碳排放相关专业问题</p>
              </div>
            ) : (
              currentMessages.map((msg, idx) => (
                <div key={idx} style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 12
                }}>
                  <div style={{
                    maxWidth: '80%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    background: msg.role === 'user' ? '#667eea' : '#f5f5f5',
                    color: msg.role === 'user' ? '#fff' : '#333'
                  }}>
                    {msg.content}
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div style={{ textAlign: 'center', color: '#999' }}>思考中...</div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div style={{ padding: 12, borderTop: '1px solid #f0f0f0', display: 'flex', gap: 8 }}>
            <Input
              value={inputMessage}
              onChange={e => setInputMessage(e.target.value)}
              onPressEnter={handleSendMessage}
              placeholder="输入您的问题..."
            />
            <Button type="primary" icon={<SendOutlined />} onClick={handleSendMessage} loading={isLoading} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ============ 主页面组件 ============

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [form] = Form.useForm();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 创建会话
  useEffect(() => {
    if (!user) {
      router.push('/login');
      return;
    }
    createSession();
  }, [user]);

  const createSession = async () => {
    try {
      const response = await sessionApi.create();
      setSession(response.data);
      message.success('会话创建成功');
    } catch (err: any) {
      console.error('[Dashboard] 创建会话失败:', err);
      message.error('会话创建失败');
    }
  };

  // 获取进度百分比
  const getProgressPercentage = () => {
    if (!session) return 0;
    const completed = Object.values(session.progress || {}).filter(s => s === 'completed').length;
    return Math.round((completed / 9) * 100);
  };

  // 切换section
  const handleSectionChange = async (section: number) => {
    if (!session) return;
    setLoading(true);
    try {
      await formApi.setCurrentSection(session.session_id, section);
      setSession(prev => prev ? { ...prev, current_section: section } : null);
    } catch (err: any) {
      console.error('[Dashboard] 切换section失败:', err);
      message.error('切换失败');
    } finally {
      setLoading(false);
    }
  };

  // 更新字段值
  const updateFieldValue = useCallback((key: string, value: any) => {
    if (!session) return;
    // 直接更新本地状态
  }, [session]);

  // 文件上传后AI提取
  const handleFileUploadAndExtract = async (file: File) => {
    if (!session) return;

    Modal.confirm({
      title: '确认上传',
      content: `正在上传文件 "${file.name}" 并进行AI数据提取，是否继续？`,
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        setLoading(true);
        message.loading({ content: '正在上传文件并提取数据...', key: 'upload' });

        // 先上传文件
        try {
          await fileApi.upload(session.session_id, session.current_section, file);
        } catch (err: any) {
          console.error('[Dashboard] 文件上传失败:', err);
          message.error({ content: '文件上传失败', key: 'upload' });
          setLoading(false);
          return;
        }

        // 调用提取API
        try {
          const formData = new FormData();
          formData.append('file', file);
          const response = await fileApi.extract(session.session_id, session.current_section, file);
          const result = response.data;

          if (result.success) {
            // 更新表单数据
            if (result.filled_data) {
              Object.entries(result.filled_data).forEach(([key, value]) => {
                form.setFieldValue(key, value);
              });
            }

            // 显示结果弹窗
            if ((window as any).showExtractResult) {
              (window as any).showExtractResult(result);
            }

            message.success({ content: '文件提取完成，数据已自动填充', key: 'upload' });
          } else {
            message.error({ content: '文件提取失败', key: 'upload' });
          }
        } catch (err: any) {
          console.error('[Dashboard] 文件提取失败:', err);
          message.error({ content: '文件提取失败: ' + (err.response?.data?.detail || err.message), key: 'upload' });
        } finally {
          setLoading(false);
        }
      }
    });
  };

  // 确认section完成
  const handleConfirmSection = async () => {
    if (!session) return;
    setLoading(true);
    try {
      const values = form.getFieldsValue();
      await formApi.confirmSection(session.session_id, session.current_section, values);
      const response = await sessionApi.get(session.session_id);
      setSession(response.data);
      message.success('部分已完成');
    } catch (err: any) {
      console.error('[Dashboard] 确认section失败:', err);
      message.error('确认失败');
    } finally {
      setLoading(false);
    }
  };

  // 登出
  const handleLogout = async () => {
    confirm({
      title: '确认登出',
      content: '确定要退出登录吗？',
      onOk: async () => {
        await logout();
        router.push('/login');
      }
    });
  };

  // 渲染字段
  const renderField = (field: FieldDef) => {
    // 条件字段检查
    if (field.conditionField) {
      const formValues = form.getFieldsValue();
      const conditionVal = formValues[field.conditionField];
      if (conditionVal === undefined || conditionVal === '' || conditionVal !== field.conditionValue) {
        return null;
      }
    }

    const label = field.unit ? `${field.label} (${field.unit})` : field.label;

    switch (field.type) {
      case 'text':
        return (
          <Form.Item key={field.key} name={field.key} label={field.label}>
            <Input placeholder={field.placeholder} />
          </Form.Item>
        );
      case 'number':
        return (
          <Form.Item key={field.key} name={field.key} label={label}>
            <InputNumber style={{ width: '100%' }} placeholder={field.placeholder} />
          </Form.Item>
        );
      case 'select':
        return (
          <Form.Item key={field.key} name={field.key} label={field.label}>
            <Select placeholder="请选择">
              {field.options?.map(opt => <Select.Option key={opt} value={opt}>{opt}</Select.Option>)}
            </Select>
          </Form.Item>
        );
      case 'file':
        return (
          <Form.Item key={field.key} label={field.label}>
            <Upload beforeUpload={(file) => { handleFileUploadAndExtract(file); return false; }} maxCount={1}>
              <Button icon={<UploadOutlined />}>点击上传文件</Button>
            </Upload>
          </Form.Item>
        );
      case 'multi-row':
        return (
          <Form.Item key={field.key} label={field.label}>
            <MultiRowTable
              field={field}
              entries={form.getFieldValue(field.key) || []}
              onChange={(key, entries) => {
                form.setFieldValue(key, entries);
              }}
            />
          </Form.Item>
        );
      default:
        return null;
    }
  };

  // 菜单项
  const menuItems: MenuProps['items'] = SECTION_NAMES.slice(1).map((name, idx) => {
    const section = idx + 1;
    const status = session?.progress?.[String(section)] || 'not_started';
    return {
      key: String(section),
      label: (
        <Space>
          <Badge status={
            status === 'completed' ? 'success' :
            status === 'in_progress' ? 'processing' : 'default'
          } />
          <span>{section}. {name}</span>
        </Space>
      ),
      icon: status === 'completed' ? <CheckCircleOutlined /> : status === 'in_progress' ? <ClockCircleOutlined /> : <FileTextOutlined />
    };
  });

  const currentFields = session ? SECTION_FIELDS[session.current_section] || [] : [];

  if (!user) return null;

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={collapsed} width={260} theme="light">
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          padding: collapsed ? 0 : '0 16px',
          borderBottom: '1px solid #f0f0f0'
        }}>
          {collapsed ? (
            <RobotOutlined style={{ fontSize: 24, color: '#667eea' }} />
          ) : (
            <Space>
              <RobotOutlined style={{ fontSize: 24, color: '#667eea' }} />
              <span style={{ fontWeight: 600, fontSize: 16 }}>碳管师收资</span>
            </Space>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[String(session?.current_section || 1)]}
          items={menuItems}
          onClick={({ key }) => handleSectionChange(Number(key))}
          style={{ borderRight: 0 }}
        />
      </Sider>

      <Layout>
        <Header style={{
          padding: '0 24px',
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)'
        }}>
          <Space>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
            />
            <Title level={4} style={{ margin: 0 }}>碳排放资料收集</Title>
          </Space>

          <Space>
            <Progress type="circle" percent={getProgressPercentage()} size={40} />
            <Text type="secondary">第{session?.current_section || 1}部分</Text>
            <Text type="secondary">|</Text>
            <Avatar icon={<UserOutlined />} />
            <Text>{user.username}</Text>
            <Button type="text" icon={<LogoutOutlined />} onClick={handleLogout}>登出</Button>
          </Space>
        </Header>

        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8 }}>
          {session && (
            <div>
              <div style={{ marginBottom: 24 }}>
                <Title level={4}>
                  <Space>
                    <Badge status="processing" />
                    第{session.current_section}部分：{SECTION_NAMES[session.current_section]}
                  </Space>
                </Title>
                <Text type="secondary">
                  {session.progress?.[String(session.current_section)] === 'completed'
                    ? '已完成'
                    : session.progress?.[String(session.current_section)] === 'in_progress'
                    ? '进行中'
                    : '未开始'}
                </Text>
              </div>

              <Form
                form={form}
                layout="vertical"
                initialValues={session.form_data?.[String(session.current_section)] || {}}
              >
                {currentFields.map(field => renderField(field))}
              </Form>

              <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
                <Button
                  type="primary"
                  icon={<CheckCircleOutlined />}
                  onClick={handleConfirmSection}
                  loading={loading}
                >
                  确认完成
                </Button>
                <Upload beforeUpload={(file) => { handleFileUploadAndExtract(file); return false; }} showUploadList={false}>
                  <Button icon={<UploadOutlined />} loading={loading}>
                    上传文件AI提取
                  </Button>
                </Upload>
                <Button
                  type="default"
                  icon={<QuestionCircleOutlined />}
                  onClick={() => setAiOpen(true)}
                >
                  AI助手
                </Button>
              </div>

              <FileUploadPanel
                sessionId={session?.session_id || ''}
                section={session?.current_section || 1}
                onDataExtracted={(data) => {
                  Object.entries(data).forEach(([key, value]) => {
                    form.setFieldValue(key, value);
                  });
                }}
              />
            </div>
          )}
        </Content>
      </Layout>

      <AIAssistant
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        sessionId={session?.session_id || null}
        currentSection={session?.current_section || 1}
      />
    </Layout>
  );
}
