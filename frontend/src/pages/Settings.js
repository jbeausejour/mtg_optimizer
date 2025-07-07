import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Switch, Select, InputNumber, Card, Divider, Typography, Space, Alert, Tooltip } from 'antd';
import { SettingOutlined, SaveOutlined, ExperimentOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';
import { useNotification } from '../utils/NotificationContext';
import api from '../utils/api';
import { useTheme } from '../utils/ThemeContext';

const { Title, Text } = Typography;
const { Option } = Select;

const Settings = () => {
  const [form] = Form.useForm();
  const { theme } = useTheme();
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(false);
  const [testMode, setTestMode] = useState(false);
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { messageApi, notificationApi } = useNotification();

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const loadingMessage = messageApi.loading('Loading settings...');
      
      const token = localStorage.getItem('accessToken');
      const response = await api.get('/settings', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      // settings with optimization defaults
      const settingsData = {
        ...response.data,
        itemsPerPage: response.data.itemsPerPage ? Number(response.data.itemsPerPage) : 20,
        priceAlertThreshold: response.data.priceAlertThreshold ? Number(response.data.priceAlertThreshold) : 10,
        
        // optimization settings
        defaultOptimizationStrategy: response.data.defaultOptimizationStrategy || 'auto',
        fallbackOptimizationStrategy: response.data.fallbackOptimizationStrategy || 'milp',
        defaultTimeLimit: response.data.defaultTimeLimit ? Number(response.data.defaultTimeLimit) : 300,
        defaultPopulationSize: response.data.defaultPopulationSize ? Number(response.data.defaultPopulationSize) : 200,
        defaultConvergenceThreshold: response.data.defaultConvergenceThreshold ? Number(response.data.defaultConvergenceThreshold) : 0.001,
        enablePerformanceMonitoring: response.data.enablePerformanceMonitoring ?? true,
        enableAlgorithmComparison: response.data.enableAlgorithmComparison ?? false,
        logOptimizationDetails: response.data.logOptimizationDetails ?? true,
      };
      
      setSettings(settingsData);
      form.setFieldsValue(settingsData);
      
      loadingMessage();
      
      return settingsData;
    } catch (error) {
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

  const testOptimizationSettings = async () => {
    setTestMode(true);
    try {
      const values = form.getFieldsValue();
      const testMessage = messageApi.loading('Testing optimization configuration...');
      
      // Test the optimization settings with a small mock problem
      const response = await api.post('/test_optimization_config', {
        optimization_config: {
          primary_algorithm: values.defaultOptimizationStrategy,
          time_limit: values.defaultTimeLimit,
          population_size: values.defaultPopulationSize,
          convergence_threshold: values.defaultConvergenceThreshold
        }
      });
      
      testMessage();
      
      notificationApi.success({
        message: 'Configuration Test Successful',
        description: `Recommended algorithm: ${response.data.recommended_algorithm}. Configuration is valid.`,
        placement: 'topRight',
      });
      
    } catch (error) {
      notificationApi.error({
        message: 'Configuration Test Failed',
        description: error.response?.data?.message || 'Invalid optimization configuration',
        placement: 'topRight',
      });
    } finally {
      setTestMode(false);
    }
  };

  const onFinish = async (values) => {
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
      
      const loadingMessage = messageApi.loading('Saving settings...');
      
      const token = localStorage.getItem('accessToken');
      
      // Process values with proper types
      const processedValues = {
        ...values,
        itemsPerPage: values.itemsPerPage ? Number(values.itemsPerPage) : 20,
        priceAlertThreshold: values.priceAlertThreshold ? Number(values.priceAlertThreshold) : 10,
        defaultTimeLimit: values.defaultTimeLimit ? Number(values.defaultTimeLimit) : 300,
        defaultPopulationSize: values.defaultPopulationSize ? Number(values.defaultPopulationSize) : 200,
        defaultConvergenceThreshold: values.defaultConvergenceThreshold ? Number(values.defaultConvergenceThreshold) : 0.001,
      };
      
      const response = await api.post(`/settings`, processedValues, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      setSettings(processedValues);
      
      loadingMessage();
      
      notificationApi.success({
        message: 'Settings saved successfully!',
        description: 'Optimization settings will be applied to future optimizations.',
        duration: 5,
        placement: 'topRight',
      });
      
      console.log('Settings saved:', response.data);
      
      return response.data;
    } catch (error) {
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
    if (changedValues.itemsPerPage && (changedValues.itemsPerPage < 5 || changedValues.itemsPerPage > 100)) {
      messageApi.warning(`Items per page should be between 5 and 100`);
    }
    
    if (changedValues.defaultTimeLimit && changedValues.defaultTimeLimit < 60) {
      messageApi.warning(`Time limit should be at least 60 seconds`);
    }
    
    if (changedValues.defaultPopulationSize && changedValues.defaultPopulationSize < 50) {
      messageApi.warning(`Population size should be at least 50 for effective optimization`);
    }
  };

  return (
    <div className={`settings ${theme}`}>
      <Title level={2}>Settings</Title>
      
      <Space direction="vertical" size="large" style={{ width: '100%', maxWidth: '1000px' }}>
        {/* Optimization Settings */}
        <Card 
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ExperimentOutlined style={{ color: '#1890ff' }} />
              <span>Optimization Configuration</span>
            </div>
          }
          extra={
            <Button 
              type="dashed" 
              icon={<InfoCircleOutlined />}
              onClick={testOptimizationSettings}
              loading={testMode}
            >
              Test Configuration
            </Button>
          }
        >
          <Form 
            form={form} 
            onFinish={onFinish}
            onValuesChange={onValuesChange}
            layout="vertical"
            preserve={false}
            initialValues={{
              defaultOptimizationStrategy: 'auto',
              fallbackOptimizationStrategy: 'milp',
              defaultTimeLimit: 300,
              defaultPopulationSize: 200,
              defaultConvergenceThreshold: 0.001,
              enablePerformanceMonitoring: true,
              enableAlgorithmComparison: false,
              logOptimizationDetails: true,
              itemsPerPage: 20,
              priceAlertThreshold: 10,
              enablePriceAlerts: false,
              scryfallApiKey: '',
              theme: 'light'
            }}
          >
            <Alert
              message="Optimization Features"
              description="These settings control the new optimization architecture. Optimization provides better algorithm selection, performance monitoring, and result quality."
              type="info"
              showIcon
              style={{ marginBottom: '16px' }}
            />

            <Form.Item
              name="defaultOptimizationStrategy"
              label="Default Optimization Algorithm"
              rules={[{ required: true, message: 'Please select a default algorithm' }]}
              tooltip="The algorithm that will be selected by default in the optimization interface"
            >
              <Select placeholder="Select default algorithm">
                <Option value="auto">🤖 Auto-Select (Recommended)</Option>
                <Option value="milp">🎯 MILP (Optimal for small problems)</Option>
                <Option value="nsga2">🧬 NSGA-II (Good for large problems)</Option>
                <Option value="moead">🔬 MOEA/D (Complex multi-objective)</Option>
                <Option value="hybrid">⚡ Hybrid (Best of both worlds)</Option>
              </Select>
            </Form.Item>

            <Form.Item
              name="fallbackOptimizationStrategy"
              label="Fallback Algorithm"
              rules={[{ required: true, message: 'Please select a fallback algorithm' }]}
              tooltip="Algorithm to use if the primary algorithm fails or times out"
            >
              <Select placeholder="Select fallback algorithm">
                <Option value="milp">MILP</Option>
                <Option value="nsga2">NSGA-II</Option>
                <Option value="hybrid">Hybrid</Option>
              </Select>
            </Form.Item>

            <Form.Item
              name="defaultTimeLimit"
              label="Default Time Limit (seconds)"
              rules={[
                { type: 'number', min: 60, max: 3600, message: 'Must be between 60 and 3600 seconds' }
              ]}
              tooltip="Default maximum time to spend on optimization before stopping"
            >
              <InputNumber 
                style={{ width: '100%' }}
                placeholder="e.g. 300 for 5 minutes" 
                min={60}
                max={3600}
                step={30}
                formatter={value => `${value}s`}
                parser={value => value.replace('s', '')}
              />
            </Form.Item>

            <Form.Item
              name="defaultPopulationSize"
              label="Default Population Size"
              rules={[
                { type: 'number', min: 50, max: 1000, message: 'Must be between 50 and 1000' }
              ]}
              tooltip="Default population size for evolutionary algorithms (NSGA-II, MOEA/D)"
            >
              <InputNumber 
                style={{ width: '100%' }}
                placeholder="e.g. 200" 
                min={50}
                max={1000}
                step={50}
              />
            </Form.Item>

            <Form.Item
              name="defaultConvergenceThreshold"
              label="Default Convergence Threshold"
              rules={[
                { type: 'number', min: 0.0001, max: 0.1, message: 'Must be between 0.0001 and 0.1' }
              ]}
              tooltip="Threshold for determining when optimization has converged (smaller = more precise)"
            >
              <InputNumber 
                style={{ width: '100%' }}
                placeholder="e.g. 0.001" 
                min={0.0001}
                max={0.1}
                step={0.001}
              />
            </Form.Item>

            <Form.Item
              name="enablePerformanceMonitoring"
              label="Enable Performance Monitoring"
              valuePropName="checked"
              tooltip="Track and display detailed performance metrics during optimization"
            >
              <Switch />
            </Form.Item>

            <Form.Item
              name="enableAlgorithmComparison"
              label="Enable Algorithm Comparison Mode"
              valuePropName="checked"
              tooltip="Run multiple algorithms in parallel for comparison (experimental feature)"
            >
              <Switch />
            </Form.Item>

            <Form.Item
              name="logOptimizationDetails"
              label="Log Detailed Optimization Information"
              valuePropName="checked"
              tooltip="Save detailed logs of optimization processes for debugging and analysis"
            >
              <Switch />
            </Form.Item>
          </Form>
        </Card>

        {/* Standard Application Settings */}
        <Card 
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <SettingOutlined />
              <span>Application Settings</span>
            </div>
          }
        >
          <Form form={form}>
            <h3>Display Settings</h3>
            <Form.Item
              name="itemsPerPage"
              label="Items Per Page"
              rules={[
                { type: 'number', min: 5, max: 100, message: 'Must be between 5 and 100' }
              ]}
              tooltip="Number of items to display per page in tables and lists"
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
              tooltip="Optional API key for Scryfall integration"
            >
              <Input.Password 
                placeholder="Optional (if applicable)" 
                visibilityToggle={false}
              />
            </Form.Item>
          </Form>
        </Card>

        {/* Performance and Monitoring */}
        <Card 
          title="Performance & Monitoring"
          extra={
            <Tooltip title="These settings affect system performance and data collection">
              <InfoCircleOutlined style={{ color: '#1890ff' }} />
            </Tooltip>
          }
        >
          <Alert
            message="Performance Impact"
            description="Monitoring and comparison features may slightly increase optimization time but provide valuable insights for algorithm selection and performance tuning."
            type="warning"
            showIcon
            style={{ marginBottom: '16px' }}
          />
          
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Text strong>Current Configuration Impact:</Text>
              <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                <li>Performance Monitoring: {settings.enablePerformanceMonitoring ? '✅ Enabled' : '❌ Disabled'}</li>
                <li>Algorithm Comparison: {settings.enableAlgorithmComparison ? '⚠️ Enabled (Experimental)' : '❌ Disabled'}</li>
                <li>Detailed Logging: {settings.logOptimizationDetails ? '✅ Enabled' : '❌ Disabled'}</li>
              </ul>
            </div>
            
            <div>
              <Text strong>Recommended Settings for:</Text>
              <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                <li><Text code>Production Use:</Text> Performance Monitoring ON, Algorithm Comparison OFF</li>
                <li><Text code>Testing/Research:</Text> All features ON for maximum insight</li>
                <li><Text code>Performance Critical:</Text> other monitoring features OFF</li>
              </ul>
            </div>
          </Space>
        </Card>

        {/* Save Button */}
        <div style={{ textAlign: 'right' }}>
          <Button 
            type="primary" 
            onClick={() => form.submit()}
            loading={loading}
            icon={<SaveOutlined />}
            size="large"
          >
            Save All Settings
          </Button>
        </div>
      </Space>
    </div>
  );
};

export default Settings;
            