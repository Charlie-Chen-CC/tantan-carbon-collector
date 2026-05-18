'use client';

import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Tabs, Select, Typography } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, BankOutlined, AimOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../store/authStore';

const { Title, Text } = Typography;
const { Option } = Select;

interface LoginForm {
  username: string;
  password: string;
}

interface RegisterForm {
  username: string;
  password: string;
  email?: string;
  enterprise_name?: string;
  industry?: string;
}

const INDUSTRY_OPTIONS = [
  '电力行业', '钢铁行业', '水泥行业', '石化行业', '化工行业',
  '有色金属行业', '造纸行业', '航空行业', '交通运输', '其他行业'
];

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('login');
  const router = useRouter();
  const { login, register } = useAuth();
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();

  const handleLogin = async (values: LoginForm) => {
    setLoading(true);
    try {
      await login(values);
      message.success('登录成功');
      router.push('/dashboard');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: RegisterForm) => {
    setLoading(true);
    try {
      await register(values);
      message.success('注册成功');
      router.push('/dashboard');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  const loginTabContent = (
    <Form<LoginForm>
      form={loginForm}
      name="login"
      onFinish={handleLogin}
      layout="vertical"
      size="large"
    >
      <Form.Item
        name="username"
        rules={[{ required: true, message: '请输入用户名' }]}
      >
        <Input
          prefix={<UserOutlined />}
          placeholder="用户名"
        />
      </Form.Item>
      <Form.Item
        name="password"
        rules={[{ required: true, message: '请输入密码' }]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="密码" />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" block loading={loading}>
          登录
        </Button>
      </Form.Item>
    </Form>
  );

  const registerTabContent = (
    <Form<RegisterForm>
      form={registerForm}
      name="register"
      onFinish={handleRegister}
      layout="vertical"
      size="large"
      initialValues={{ industry: '其他行业' }}
    >
      <Form.Item
        name="username"
        label="用户名"
        rules={[
          { required: true, message: '请输入用户名' },
          { min: 3, message: '用户名至少3个字符' }
        ]}
      >
        <Input prefix={<UserOutlined />} placeholder="请输入用户名" />
      </Form.Item>
      <Form.Item
        name="password"
        label="密码"
        rules={[
          { required: true, message: '请输入密码' },
          { min: 6, message: '密码至少6个字符' }
        ]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
      </Form.Item>
      <Form.Item
        name="email"
        label="邮箱"
        rules={[
          { type: 'email', message: '请输入有效的邮箱地址' }
        ]}
      >
        <Input prefix={<MailOutlined />} placeholder="请输入邮箱（选填）" />
      </Form.Item>
      <Form.Item
        name="enterprise_name"
        label="企业名称"
      >
        <Input prefix={<BankOutlined />} placeholder="请输入企业名称（选填）" />
      </Form.Item>
      <Form.Item
        name="industry"
        label="所属行业"
      >
        <Select placeholder="请选择所属行业">
          {INDUSTRY_OPTIONS.map(industry => (
            <Option key={industry} value={industry}>{industry}</Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" block loading={loading}>
          注册
        </Button>
      </Form.Item>
    </Form>
  );

  const tabItems = [
    {
      key: 'login',
      label: '登录',
      children: loginTabContent,
    },
    {
      key: 'register',
      label: '注册',
      children: registerTabContent,
    },
  ];

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '20px'
    }}>
      <Card
        style={{
          width: '100%',
          maxWidth: 420,
          boxShadow: '0 14px 40px rgba(0,0,0,0.2)',
          borderRadius: 12,
        }}
        styles={{ body: { padding: '32px 32px 24px' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 64,
            height: 64,
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: 16,
            marginBottom: 16
          }}>
            <AimOutlined style={{ fontSize: 32, color: '#fff' }} />
          </div>
          <Title level={3} style={{ margin: 0 }}>碳管师收资系统</Title>
          <Text type="secondary">Multi-Agent碳排放资料收集系统</Text>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          centered
        />
      </Card>
    </div>
  );
}