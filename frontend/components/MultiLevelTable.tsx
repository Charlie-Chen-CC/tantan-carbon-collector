'use client';

/**
 * MultiLevelTable - 嵌套对象字段渲染器（P0-6 修复）
 *
 * 用途：渲染 type: 'nested' 的字段。与 MultiRowTable 的区别：
 *   - multi-row：数组形式，多行重复子字段
 *   - nested：单条嵌套对象（单个 form 包含 N 个子字段）
 *
 * 字段定义来源：NESTED_FIELD_SCHEMA[field.key]（sub_fields）
 * Form state：扁平 key（与后端 NESTED_FIELD_TRANSFORMERS 输出对齐）
 *   例：freshWater 字段 → form 存 { freshWaterCaliber, freshWaterAmount, freshWaterUnit }
 *       渲染为 1 个 Card 含 3 个 Form.Item
 *
 * 用法：
 *   <Form.Item name="freshWater" label="新鲜水">
 *     <MultiLevelTable field={field} />
 *   </Form.Item>
 */
import { Form, Input, Card, Space, Typography } from 'antd';
import { FieldDef, NESTED_FIELD_SCHEMA } from '../config/sectionConfig';

const { Text } = Typography;

export interface MultiLevelTableProps {
  field: FieldDef;
}

export default function MultiLevelTable({ field }: MultiLevelTableProps) {
  const subFields = NESTED_FIELD_SCHEMA[field.key] || [];

  if (subFields.length === 0) {
    return (
      <Card size="small" title={field.label}>
        <Text type="warning">
          ⚠️ 字段 {field.key} 未在 NESTED_FIELD_SCHEMA 中定义子字段（P0-6 守门会失败）
        </Text>
      </Card>
    );
  }

  return (
    <Card size="small" title={field.label}>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {subFields.map((sub) => {
          // form 存为扁平 key：{parentKey}{SubKey 首字母大写}
          // 与后端 NESTED_FIELD_TRANSFORMERS 输出对齐（freshWaterCaliber 等）
          const formName = `${field.key}${sub.key.charAt(0).toUpperCase()}${sub.key.slice(1)}`;
          return (
            <Form.Item
              key={formName}
              name={formName}
              label={sub.label}
              style={{ marginBottom: 0 }}
            >
              <Input placeholder={sub.placeholder || `请输入${sub.label}`} />
            </Form.Item>
          );
        })}
      </Space>
    </Card>
  );
}
