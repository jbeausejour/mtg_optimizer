import React, { useState, useEffect } from 'react';
import { Table, Card, Typography, Button, Space, Modal, Form, Input, message, Spin, Tag, Switch, Select, Popconfirm } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import { EditOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import api from '../utils/api';

const { Title } = Typography;

const SiteManagement = () => {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const { theme } = useTheme();
  const [editingRecord, setEditingRecord] = useState(null);
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [addForm] = Form.useForm();

  useEffect(() => {
    fetchSites();
  }, []);

  const fetchSites = async () => {
    try {
      const response = await api.get('/sites');
      setSites(response.data);
    } catch (error) {
      console.error('Error fetching sites:', error);
      message.error('Failed to fetch sites');
    } finally {
      setLoading(false);
    }
  };

  const getUniqueCountries = () => {
    const countries = [...new Set(sites.map(site => site.country))];
    return countries.filter(Boolean).map(country => ({ text: country, value: country }));
  };

  const handleEdit = (record) => {
    setEditingRecord(record);
    editForm.setFieldsValue(record);
    setIsEditModalVisible(true);
  };

  const handleAdd = () => {
    addForm.resetFields();
    setIsAddModalVisible(true);
  };

  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      const response = await api.put(`/sites/${editingRecord.id}`, values);
      
      // Handle different response statuses
      switch (response.data.status) {
        case 'success':
          message.success(response.data.message);
          setSites(sites.map(site => 
            site.id === editingRecord.id ? { ...site, ...values } : site
          ));
          setIsEditModalVisible(false);
          break;
        case 'info':
          message.info(response.data.message);
          setIsEditModalVisible(false);
          break;
        case 'warning':
          message.warning(response.data.message);
          break;
        default:
          message.error('Failed to update site');
      }
    } catch (error) {
      if (error.response?.data?.message) {
        message.warning(error.response.data.message);
      } else {
        message.error('Failed to update site');
      }
    }
  };

  const handleAddSubmit = async () => {
    try {
      const values = await addForm.validateFields();
      const response = await api.post('/sites', values);
      if (response.data) {
        setSites([...sites, response.data]);
        message.success('Site added successfully');
        setIsAddModalVisible(false);
      }
    } catch (error) {
      message.error('Failed to add site');
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.delete(`/sites/${id}`);
      setSites(sites.filter(site => site.id !== id));
      message.success('Site deleted successfully');
    } catch (error) {
      message.error('Failed to delete site');
    }
  };

  const getTypeColor = (type) => {
    switch (type) {
      case 'Primary':
        return 'green';
      case 'Extended':
        return 'blue';
      case 'Marketplace':
        return 'purple';
      case 'NoInventory':
        return 'orange';
      case 'NotWorking':
        return 'red';
      default:
        return 'default';
    }
  };

  const getCountryColor = (country) => {
    switch (country?.toLowerCase()) {
      case 'usa':
      case 'united states':
        return 'blue';
      case 'canada':
        return 'green';
      case 'france':
        return 'cyan';
      case 'germany':
        return 'gold';
      case 'japan':
        return 'volcano';
      case 'korea':
        return 'geekblue';
      case 'italy':
        return 'red';
      default:
        return 'default';
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <Input
            placeholder="Search site name"
            value={selectedKeys[0]}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            onPressEnter={confirm}
            style={{ width: 188, marginBottom: 8, display: 'block' }}
          />
          <Button onClick={confirm} size="small" style={{ width: 90, marginRight: 8 }}>Filter</Button>
          <Button onClick={clearFilters} size="small" style={{ width: 90 }}>Reset</Button>
        </div>
      ),
      onFilter: (value, record) => record.name.toLowerCase().includes(value.toLowerCase()),
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
      sorter: (a, b) => a.method?.localeCompare(b.method),
      filters: [
        { text: 'Add to cart', value: 'add_to_cart' },
        { text: 'Shopify', value: 'Shopify' },
        { text: 'Other', value: 'other' },
      ],
      onFilter: (value, record) => record.method === value,
    },
    {
      title: 'Country',
      dataIndex: 'country',
      key: 'country',
      sorter: (a, b) => a.country?.localeCompare(b.country),
      filters: getUniqueCountries(),
      onFilter: (value, record) => record.country === value,
      render: (country) => (
        <Tag color={getCountryColor(country)}>
          {country || 'Unknown'}
        </Tag>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      sorter: (a, b) => a.type?.localeCompare(b.type),
      filters: [
        { text: 'Primary', value: 'Primary' },
        { text: 'Extended', value: 'Extended' },
        { text: 'Marketplace', value: 'Marketplace' },
        { text: 'No Inventory', value: 'NoInventory' },
        { text: 'Not Working', value: 'NotWorking' },
      ],
      onFilter: (value, record) => record.type === value,
      render: (type) => (
        <Tag color={getTypeColor(type)}>
          {type === 'NoInventory' ? 'No Inventory' : 
           type === 'NotWorking' ? 'Not Working' : 
           type}
        </Tag>
      ),
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
      render: (text) => <a href={text} target="_blank" rel="noopener noreferrer">{text}</a>,
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <Input
            placeholder="Search URL"
            value={selectedKeys[0]}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            onPressEnter={confirm}
            style={{ width: 188, marginBottom: 8, display: 'block' }}
          />
          <Button onClick={confirm} size="small" style={{ width: 90, marginRight: 8 }}>Filter</Button>
          <Button onClick={clearFilters} size="small" style={{ width: 90 }}>Reset</Button>
        </div>
      ),
      onFilter: (value, record) => record.url.toLowerCase().includes(value.toLowerCase()),
    },
    {
      title: 'Status',
      dataIndex: 'active',
      key: 'active',
      render: (active) => (
        <Tag color={active ? 'green' : 'red'}>
          {active ? 'Active' : 'Inactive'}
        </Tag>
      ),
      filters: [
        { text: 'Active', value: true },
        { text: 'Inactive', value: false },
      ],
      onFilter: (value, record) => record.active === value,
      sorter: (a, b) => Number(a.active) - Number(b.active),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button 
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            Edit
          </Button>
          <Popconfirm
            title="Are you sure you want to delete this site?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (loading) return <Spin size="large" />;

  const renderFormItems = (form) => (
    <>
      <Form.Item
        name="name"
        label="Name"
        rules={[{ required: true }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="url"
        label="URL"
        rules={[{ required: true, type: 'url' }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="method"
        label="Method"
        rules={[{ required: true }]}
      >
        <Select>
          <Select.Option value="add_to_cart">add_to_cart</Select.Option>
          <Select.Option value="Shopify">Shopify</Select.Option>
          <Select.Option value="other">other</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item
        name="country"
        label="Country"
      >
        <Input />
      </Form.Item>
      <Form.Item
        name="type"
        label="Type"
        rules={[{ required: true }]}
      >
        <Select>
          <Select.Option value="Primary">Primary</Select.Option>
          <Select.Option value="Extended">Extended</Select.Option>
          <Select.Option value="Marketplace">Marketplace</Select.Option>
          <Select.Option value="NoInventory">No Inventory</Select.Option>
          <Select.Option value="NotWorking">Not Working</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item
        name="active"
        label="Active"
        valuePropName="checked"
        initialValue={form === 'add'}
      >
        <Switch />
      </Form.Item>
    </>
  );

  return (
    <div className={`site-management section ${theme}`}>
      <Title level={2}>Site Management</Title>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleAdd}
        >
          Add Site
        </Button>
      </div>
      <Card>
        <Table
          dataSource={sites}
          columns={columns}
          rowKey="id"
          pagination={false}
        />
      </Card>

      {/* Edit Modal */}
      <Modal
        title="Edit Site"
        open={isEditModalVisible}
        onOk={handleEditSubmit}
        onCancel={() => setIsEditModalVisible(false)}
      >
        <Form form={editForm} layout="vertical">
          {renderFormItems('edit')}
        </Form>
      </Modal>

      {/* Add Modal */}
      <Modal
        title="Add New Site"
        open={isAddModalVisible}
        onOk={handleAddSubmit}
        onCancel={() => setIsAddModalVisible(false)}
      >
        <Form form={addForm} layout="vertical">
          {renderFormItems('add')}
        </Form>
      </Modal>
    </div>
  );
};

export default SiteManagement;
