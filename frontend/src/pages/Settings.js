import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Switch, Select, message } from 'antd';
import axios from 'axios';

const { Option } = Select;

const Settings = () => {
  const [form] = Form.useForm();
  const [settings, setSettings] = useState({});

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/settings`);
      setSettings(response.data);
      form.setFieldsValue(response.data);
    } catch (error) {
      message.error('Failed to fetch settings');
    }
  };

  const onFinish = async (values) => {
    try {
      await axios.post(`${process.env.REACT_APP_API_URL}/settings`, values);
      message.success('Settings updated successfully');
    } catch (error) {
      message.error('Failed to update settings');
    }
  };

  return (
    <div className="settings">
      <h1>Settings</h1>
      <Form form={form} onFinish={onFinish} layout="vertical">
        <Form.Item name="defaultOptimizationStrategy" label="Default Optimization Strategy">
          <Select>
            <Option value="milp">MILP</Option>
            <Option value="nsga_ii">NSGA-II</Option>
            <Option value="hybrid">Hybrid</Option>
          </Select>
        </Form.Item>
        <Form.Item name="priceAlertThreshold" label="Price Alert Threshold (%)" type="number">
          <Input />
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