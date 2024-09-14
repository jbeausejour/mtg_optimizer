import React, { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';
import api from '../utils/api';

const Register = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const onFinish = async (values) => {
    setLoading(true);
    try {
      await api.post('/register', values);
      message.success('Registration successful');
      // Optionally log the user in immediately after registration
      await login(values);
      navigate('/');
    } catch (error) {
      message.error('Registration failed: ' + (error.response?.data?.message || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form name="register" onFinish={onFinish}>
      <Form.Item name="username" rules={[{ required: true, message: 'Please input your username!' }]}>
        <Input placeholder="Username" />
      </Form.Item>
      <Form.Item name="email" rules={[{ required: true, type: 'email', message: 'Please input a valid email!' }]}>
        <Input placeholder="Email" />
      </Form.Item>
      <Form.Item name="password" rules={[{ required: true, message: 'Please input your password!' }]}>
        <Input.Password placeholder="Password" />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>
          Register
        </Button>
      </Form.Item>
    </Form>
  );
};

export default Register;