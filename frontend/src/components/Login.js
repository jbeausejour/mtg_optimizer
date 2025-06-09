import React, { useState, useEffect } from 'react';
import { Form, Input, Button, message, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';
import './Login.css';  // Using the global CSS

const { Title } = Typography;

const Login = () => { // Add onLogin as a prop
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  // Hide navigation when the login page is loaded
  useEffect(() => {
    const navbar = document.querySelector('.navbar');
    if (navbar) {
      navbar.style.display = 'none';
    }

    // Clean up: restore navbar visibility when unmounting
    return () => {
      const navbar = document.querySelector('.navbar');
      if (navbar) {
        navbar.style.display = 'block';
      }
    };
  }, []);

  const onFinish = async (values) => {
    setLoading(true);
    try {
      await login(values);
      message.success('Login successful');
      navigate('/');
    } catch (error) {
      message.error('Login failed: ' + (error.response?.data?.message || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <Title level={2}>Login</Title>
        <Form name="login" onFinish={onFinish}>
          <Form.Item
            name="username"
            rules={[{ required: true, message: 'Please input your username!' }]}
          >
            <Input placeholder="Username" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Please input your password!' }]}
          >
            <Input.Password placeholder="Password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Log in
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
};

export default Login;
