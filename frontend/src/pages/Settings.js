import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Switch, Select, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';
import api from '../utils/api';

const { Option } = Select;

const Settings = ({ userId }) => {
  const [form] = Form.useForm();
  const [settings, setSettings] = useState({});
  const navigate = useNavigate();
  const { logout } = useAuth();

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await api.get('/settings', {
        params: { user_id: userId }
      });
      console.log('Fetched settings:', response.data);
      setSettings(response.data);
      form.setFieldsValue(response.data);
    } catch (error) {
      if (error.response) {
        switch (error.response.status) {
          case 401:
            message.error('Your session has expired. Please log in again.');
            logout();
            navigate('/login');
            break;
          case 403:
            message.error('You do not have permission to access settings.');
            break;
          default:
            message.error('An error occurred while fetching settings.');
        }
      } else if (error.request) {
        message.error('No response received from the server. Please try again later.');
      } else {
        message.error('An unexpected error occurred.');
      }
      console.error('Error fetching settings:', error);
    }
  };

  const onFinish = async (values) => {
    try {
      const token = localStorage.getItem('accessToken');
      await api.post(`/settings`, { ...values, user_id: userId }, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      message.success('Settings updated successfully');
    } catch (error) {
      if (error.response) {
        switch (error.response.status) {
          case 401:
            message.error('Your session has expired. Please log in again.');
            logout();
            navigate('/login');
            break;
          case 403:
            message.error('You do not have permission to update settings.');
            break;
          default:
            message.error('An error occurred while updating settings.');
        }
      } else if (error.request) {
        message.error('No response received from the server. Please try again later.');
      } else {
        message.error('An unexpected error occurred.');
      }
      console.error('Error updating settings:', error);
    }
  };

  return (
    <div className="settings">
      <h1>Settings</h1>
      <Form form={form} onFinish={onFinish} layout="vertical">
        <Form.Item name="defaultOptimizationStrategy" label="Default Optimization Strategy">
          <Select>
            <Option value="milp">MILP</Option>
            <Option value="nsga-ii">NSGA-II</Option>
            <Option value="hybrid">Hybrid</Option>
          </Select>
        </Form.Item>
        <Form.Item name="priceAlertThreshold" label="Price Alert Threshold (%)">
          <Input type="number" />
        </Form.Item>
        <Form.Item name="enablePriceAlerts" label="Enable Price Alerts" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="scryfallApiKey" label="Scryfall API Key">
          <Input />
        </Form.Item>
        <Form.Item name="theme" label="Theme">
          <Select>
            <Option value="light">Light</Option>
            <Option value="dark">Dark</Option>
          </Select>
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit">
            Save Settings
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
};

export default Settings;
