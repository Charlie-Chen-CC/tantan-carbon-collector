'use client';

/**
 * 单 section 表单渲染
 *
 * 包含：
 *   - renderField 字段渲染（text/number/select/file/multi-row）
 *   - 条件字段（conditionField/conditionValue）
 *   - MultiRowTable 多行动态表格
 *
 * Form 容器由父组件提供（避免 useFormInstance 跨组件失效）
 */
import {
  Form,
  Input,
  InputNumber,
  Select,
  Button,
  Upload,
  Card,
  Table,
  Space,
  Typography,
} from 'antd';
import { UploadOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import type { TableProps } from 'antd';
import { FieldDef } from '../config/sectionConfig';

const { Text } = Typography;

interface MultiRowEntry {
  id: string;
  [subKey: string]: string | number | null;
}

function genId(): string {
  return Math.random().toString(36).substring(2, 9);
}

interface MultiRowTableProps {
  field: FieldDef;
}

function MultiRowTable({ field }: MultiRowTableProps) {
  const form = Form.useFormInstance();
  const entries: MultiRowEntry[] = Form.useWatch(field.key, form) || [];

  const handleAddRow = () => {
    const shouldBlock = field.maxRows !== -1 && entries.length >= (field.maxRows as number);
    if (shouldBlock) return;
    const newEntry: MultiRowEntry = { id: genId() };
    field.fields?.forEach((f) => {
      newEntry[f.key] = '';
    });
    form.setFieldValue(field.key, [...entries, newEntry]);
  };

  const handleRemoveRow = (id: string) => {
    form.setFieldValue(
      field.key,
      entries.filter((e) => e.id !== id),
    );
  };

  const handleSubFieldChange = (id: string, subKey: string, value: string) => {
    form.setFieldValue(
      field.key,
      entries.map((e) => (e.id === id ? { ...e, [subKey]: value } : e)),
    );
  };

  const columns: TableProps<any>['columns'] =
    field.fields?.map((f) => ({
      title: f.label,
      dataIndex: f.key,
      key: f.key,
      width: 180,
      render: (_: any, record: MultiRowEntry) => {
        if (f.type === 'select') {
          return (
            <Select
              value={String(record[f.key] || '')}
              onChange={(val) => handleSubFieldChange(record.id, f.key, val)}
              placeholder={f.placeholder}
              style={{ width: '100%' }}
            >
              {f.options?.map((opt) => (
                <Select.Option key={opt} value={opt}>
                  {opt}
                </Select.Option>
              ))}
            </Select>
          );
        }
        if (f.type === 'number') {
          return (
            <InputNumber
              value={Number(record[f.key]) || 0}
              onChange={(val) => handleSubFieldChange(record.id, f.key, String(val || ''))}
              placeholder={f.placeholder}
              style={{ width: '100%' }}
            />
          );
        }
        return (
          <Input
            value={String(record[f.key] || '')}
            onChange={(e) => handleSubFieldChange(record.id, f.key, e.target.value)}
            placeholder={f.placeholder}
          />
        );
      },
    })) || [];

  columns.push({
    title: '',
    dataIndex: 'action',
    key: 'action',
    width: 60,
    render: (_: any, record: MultiRowEntry) => (
      <Button
        type="text"
        danger
        icon={<DeleteOutlined />}
        onClick={() => handleRemoveRow(record.id)}
      />
    ),
  });

  return (
    <Card
      size="small"
      title={field.label}
      extra={
        <Space>
          <Text type="secondary">
            {entries.length}/{field.maxRows || '∞'}
          </Text>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleAddRow}
            disabled={field.maxRows !== -1 && entries.length >= (field.maxRows as number)}
          >
            添加
          </Button>
        </Space>
      }
    >
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
          暂无数据，
          <Button type="link" onClick={handleAddRow}>
            点击添加
          </Button>
        </div>
      )}
    </Card>
  );
}

export interface FormSectionProps {
  fields: FieldDef[];
  watchedValues: Record<string, any>;
  onFileUpload: (file: File) => void;
}

/**
 * 把 SECTION_FIELDS 渲染为 Form.Item 列表。
 * Form 容器必须在父组件提供；这里不包含 Form 标签本身，
 * 这样父组件可以挂载 form 实例、设置 key=、控制 buttons。
 */
export default function FormSection({ fields, watchedValues, onFileUpload }: FormSectionProps) {
  const renderField = (field: FieldDef) => {
    if (field.conditionField) {
      const conditionVal = watchedValues?.[field.conditionField];
      if (
        conditionVal === undefined ||
        conditionVal === '' ||
        conditionVal !== field.conditionValue
      ) {
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
              {field.options?.map((opt) => (
                <Select.Option key={opt} value={opt}>
                  {opt}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        );
      case 'file':
        return (
          <Form.Item key={field.key} label={field.label}>
            <Upload
              beforeUpload={(file) => {
                onFileUpload(file);
                return false;
              }}
              maxCount={1}
            >
              <Button icon={<UploadOutlined />}>点击上传文件</Button>
            </Upload>
          </Form.Item>
        );
      case 'multi-row':
        return (
          <Form.Item key={field.key} name={field.key} label={field.label} valuePropName="value">
            <MultiRowTable field={field} />
          </Form.Item>
        );
      default:
        return null;
    }
  };

  return <>{fields.map((f) => renderField(f))}</>;
}
