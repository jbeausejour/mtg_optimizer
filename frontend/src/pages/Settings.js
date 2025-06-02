import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Switch, Select, InputNumber, Card, Divider } from 'antd';
import { SettingOutlined, SaveOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';
import { useNotification } from '../utils/NotificationContext';
import api from '../utils/api';

const { Option } = Select;

const Settings = () => {
  const [form] = Form.useForm();
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { messageApi, notificationApi } = useNotification(); // Direct APIs only

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      // Show loading message
      const loadingMessage = messageApi.loading('Loading settings...');
      
      // Fetch settings from API
      const token = localStorage.getItem('accessToken');
      const response = await api.get('/settings', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      // Ensure numeric fields are properly converted
      const settingsData = {
        ...response.data,
        itemsPerPage: response.data.itemsPerPage ? Number(response.data.itemsPerPage) : 20,
        priceAlertThreshold: response.data.priceAlertThreshold ? Number(response.data.priceAlertThreshold) : 10,
      };
      
      // Update state and form
      setSettings(settingsData);
      form.setFieldsValue(settingsData);
      
      // Hide loading message
      loadingMessage();
      
      return settingsData;
    } catch (error) {
      // Handle errors with direct notification API
      if (error.response) {
        const status = error.response.status;
        
        if (status === 401) {
          notificationApi.warning({
            message: 'Session Expired',
            description: 'Please log in again to continue',
            placement: 'topRight',
          });
          logout();
          navigate('/login');
        } else if (status === 403) {
          notificationApi.error({
            message: 'Permission Denied',
            description: 'You do not have permission to access settings',
            placement: 'topRight',
          });
        } else {
          notificationApi.error({
            message: 'Failed to load settings',
            description: error.response.data?.message || 'An error occurred',
            placement: 'topRight',
          });
        }
      } else if (error.request) {
        notificationApi.error({
          message: 'Network Error',
          description: 'Please check your internet connection and try again',
          placement: 'topRight',
        });
      } else {
        notificationApi.error({
          message: 'Error',
          description: error.message || 'An unexpected error occurred',
          placement: 'topRight',
        });
      }
      
      console.error('Error fetching settings:', error);
    }
  };

  const onFinish = async (values) => {
    // Validate form before submission
    try {
      await form.validateFields();
    } catch (errorInfo) {
      notificationApi.error({
        message: 'Validation Error',
        description: 'Please check all required fields',
        placement: 'topRight',
      });
      return;
    }

    try {
      setLoading(true);
      
      // Show loading message
      const loadingMessage = messageApi.loading('Saving settings...');
      
      const token = localStorage.getItem('accessToken');
      
      // Ensure numeric values are sent as numbers
      const processedValues = {
        ...values,
        itemsPerPage: values.itemsPerPage ? Number(values.itemsPerPage) : 20,
        priceAlertThreshold: values.priceAlertThreshold ? Number(values.priceAlertThreshold) : 10,
      };
      
      // Save settings to API
      const response = await api.post(`/settings`, processedValues, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      // Update local state
      setSettings(processedValues);
      
      // Hide loading message
      loadingMessage();
      
      // Show success notification
      notificationApi.success({
        message: 'Settings saved successfully!',
        description: 'Changes will take effect immediately.',
        duration: 5,
        placement: 'topRight',
      });
      
      console.log('Settings saved:', response.data);
      
      return response.data;
    } catch (error) {
      // Handle errors with direct notification API
      if (error.response) {
        const status = error.response.status;
        
        if (status === 401) {
          notificationApi.warning({
            message: 'Session Expired',
            description: 'Please log in again to continue',
            placement: 'topRight',
          });
          logout();
          navigate('/login');
        } else if (status === 403) {
          notificationApi.error({
            message: 'Permission Denied',
            description: 'You do not have permission to save settings',
            placement: 'topRight',
          });
        } else {
          notificationApi.error({
            message: 'Failed to save settings',
            description: error.response.data?.message || 'An error occurred',
            placement: 'topRight',
          });
        }
      } else if (error.request) {
        notificationApi.error({
          message: 'Network Error',
          description: 'Please check your internet connection and try again',
          placement: 'topRight',
        });
      } else {
        notificationApi.error({
          message: 'Error',
          description: error.message || 'An unexpected error occurred',
          placement: 'topRight',
        });
      }
      
      console.error('Error saving settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const onValuesChange = (changedValues, allValues) => {
    // Optional: Show real-time validation feedback
    if (changedValues.itemsPerPage && (changedValues.itemsPerPage < 5 || changedValues.itemsPerPage > 100)) {
      // Could show a warning here if needed using direct API
      messageApi.warning(`Items per page should be between 5 and 100`);
    }
  };

  return (
    <div className="settings" style={{ padding: '24px' }}>
      <Card 
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <SettingOutlined />
            <span>Application Settings</span>
          </div>
        }
        style={{ maxWidth: '800px', margin: '0 auto' }}
      >
        <Form 
          form={form} 
          onFinish={onFinish}
          onValuesChange={onValuesChange}
          layout="vertical"
          preserve={false}
          initialValues={{
            defaultOptimizationStrategy: 'milp',
            priceAlertThreshold: 10,
            itemsPerPage: 20,
            enablePriceAlerts: false,
            scryfallApiKey: '',
            theme: 'light'
          }}
        >
          <h3>Optimization Settings</h3>
          <Form.Item
            name="defaultOptimizationStrategy"
            label="Default Optimization Strategy"
            rules={[{ required: true, message: 'Please select a strategy' }]}
            tooltip="The default algorithm to use for portfolio optimization"
          >
            <Select placeholder="Select a strategy">
              <Option value="milp">MILP (Mixed Integer Linear Programming)</Option>
              <Option value="nsga-ii">NSGA-II (Multi-objective Genetic Algorithm)</Option>
              <Option value="hybrid">Hybrid (Combines multiple approaches)</Option>
            </Select>
          </Form.Item>

          <Divider />
          
          <h3>Display Settings</h3>
          <Form.Item
            name="itemsPerPage"
            label="Items Per Page"
            rules={[
              { type: 'number', min: 5, max: 100, message: 'Must be between 5 and 100' }
            ]}
            tooltip="Number of items to display per page in tables and lists throughout the application"
          >
            <InputNumber 
              style={{ width: '100%' }}
              placeholder="e.g. 20" 
              min={5}
              max={100}
              step={5}
            />
          </Form.Item>

          <Form.Item
            name="theme"
            label="Theme"
            rules={[{ required: true, message: 'Please select a theme' }]}
            tooltip="Choose your preferred visual theme"
          >
            <Select placeholder="Choose theme">
              <Option value="light">Light Mode</Option>
              <Option value="dark">Dark Mode</Option>
            </Select>
          </Form.Item>

          <Divider />
          
          <h3>Price Alert Settings</h3>
          <Form.Item
            name="enablePriceAlerts"
            label="Enable Price Alerts"
            valuePropName="checked"
            tooltip="Receive notifications when significant price changes occur"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            name="priceAlertThreshold"
            label="Price Alert Threshold (%)"
            rules={[
              { type: 'number', min: 0, max: 100, message: 'Must be between 0 and 100' }
            ]}
            tooltip="Trigger alerts when price changes exceed this percentage"
          >
            <InputNumber 
              style={{ width: '100%' }}
              placeholder="e.g. 10 for 10%" 
              min={0}
              max={100}
              step={1}
              formatter={value => `${value}%`}
              parser={value => value.replace('%', '')}
            />
          </Form.Item>

          <Divider />
          
          <h3>API Settings</h3>
          <Form.Item
            name="scryfallApiKey"
            label="Scryfall API Key"
            tooltip="Optional API key for enhanced Scryfall integration"
          >
            <Input.Password 
              placeholder="Optional (if applicable)" 
              visibilityToggle={false}
            />
          </Form.Item>
          
          <Form.Item style={{ marginTop: '32px', textAlign: 'right' }}>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading}
              icon={<SaveOutlined />}
              size="large"
            >
              Save Settings
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Settings;