import React, { useState, useEffect, useRef } from 'react';
import { Table, Card, Typography, Button, Space, Modal, Form, Input, message, Spin, Tag, Switch, Select, Popconfirm } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import { EditOutlined, PlusOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import api from '../utils/api';

const { Title } = Typography;

const SiteManagement = ({ userId }) => {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const { theme } = useTheme();
  const [editingRecord, setEditingRecord] = useState(null);
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [addForm] = Form.useForm();
  const [editMethodValue, setEditMethodValue] = useState('');
  const [addMethodValue, setAddMethodValue] = useState('');
  const [filteredInfo, setFilteredInfo] = useState({});
  const [searchText, setSearchText] = useState({});
  const [searchedColumn, setSearchedColumn] = useState('');
  const searchInput = useRef(null);

  useEffect(() => {
    fetchSites();
  }, []);

  const fetchSites = async () => {
    try {
      const response = await api.get('/sites', {
        params: { user_id: userId }
      });
      setSites(response.data);
    } catch (error) {
      console.error('Error fetching sites:', error);
      message.error('Failed to fetch sites');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (selectedKeys, confirm, dataIndex) => {
    confirm();
    setSearchText({ ...searchText, [dataIndex]: selectedKeys[0] });
    setSearchedColumn(dataIndex);
  };

  const handleReset = (clearFilters, dataIndex) => {
    clearFilters();
    setSearchText({ ...searchText, [dataIndex]: '' });
  };

  const getColumnSearchProps = (dataIndex) => ({
    filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
      <div style={{ padding: 8 }}>
        <Input
          ref={node => {
            if (node && !searchInput.current) {
              searchInput.current = {};
            }
            if (node) {
              searchInput.current[dataIndex] = node;
            }
          }}
          placeholder={`Search ${dataIndex}`}
          value={selectedKeys[0]}
          onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
          onPressEnter={() => handleSearch(selectedKeys, confirm, dataIndex)}
          style={{ width: 188, marginBottom: 8, display: 'block' }}
        />
        <Space>
          <Button
            type="primary"
            onClick={() => handleSearch(selectedKeys, confirm, dataIndex)}
            icon={<SearchOutlined />}
            size="small"
            style={{ width: 90 }}
          >
            Search
          </Button>
          <Button onClick={() => handleReset(clearFilters, dataIndex)} size="small" style={{ width: 90 }}>
            Reset
          </Button>
        </Space>
      </div>
    ),
    filterIcon: filtered => <SearchOutlined style={{ color: filtered ? '#1890ff' : undefined }} />,
    filteredValue: filteredInfo[dataIndex] || null,
    onFilter: (value, record) => 
      record[dataIndex]
        ? record[dataIndex].toString().toLowerCase().includes(value.toLowerCase())
        : ''
  });

  const handleResetFilters = () => {
    setFilteredInfo({});
    setSearchText({});
    setSearchedColumn('');
    if (searchInput.current) {
      Object.values(searchInput.current).forEach(input => {
        if (input) {
          input.value = '';
        }
      });
    }
    fetchSites();
  };


  const getUniqueCountries = () => {
    return [
      { text: 'Canada', value: 'Canada' },
      { text: 'USA', value: 'USA' },
      { text: 'Others', value: 'Others' }
    ];
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

  const handleEdit = (record) => {
    setEditingRecord(record);
    setEditMethodValue(record.method);
    editForm.setFieldsValue(record);
    setIsEditModalVisible(true);
  };

  const handleAdd = () => {
    addForm.resetFields();
    setAddMethodValue('');
    setIsAddModalVisible(true);
  };

  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      const response = await api.put(`/sites/${editingRecord.id}`, { ...values, user_id: userId }); // Add user ID
      
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
      const response = await api.post('/sites', { ...values}); 
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
      await api.delete(`/sites/${id}`, {
        params: { user_id: userId } // Add user ID
      });
      setSites(sites.filter(site => site.id !== id));
      message.success('Site deleted successfully');
    } catch (error) {
      message.error('Failed to delete site');
    }
  };
  const handleMethodChange = (value, formType) => {
    if (formType === 'edit') {
      setEditMethodValue(value);
    } else {
      setAddMethodValue(value);
    }

    const currentForm = formType === 'edit' ? editForm : addForm;
    if (value !== 'shopify' && value !== 'f2f') {
      currentForm.setFieldsValue({
        api_url: undefined
      });
    }
    currentForm.validateFields(['method']); 
  };

  const renderFormItems = (form) => {
    const methodValue = form === 'edit' ? editMethodValue : addMethodValue;

    return (
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
          <Select onChange={(value) => handleMethodChange(value, form)}>
            <Select.Option value="crystal">Crystal</Select.Option>
            <Select.Option value="shopify">Shopify</Select.Option>
            <Select.Option value="f2f">F2F</Select.Option>
            <Select.Option value="scrapper">Scrapper</Select.Option>
            <Select.Option value="other">Other</Select.Option>
          </Select>
        </Form.Item>
        {(methodValue === 'shopify' || methodValue === 'f2f') && (
          <Form.Item
            name="api_url"
            label="API URL"
            rules={[{ required: true, message: 'API URL is required for Shopify sites' }]}
          >
            <Input />
          </Form.Item>
        )}
        <Form.Item name="country" label="Country" rules={[{ required: true }]}>
          <Select>
            <Select.Option value="USA">USA</Select.Option>
            <Select.Option value="Canada">Canada</Select.Option>
            <Select.Option value="Others">Others</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item name="type" label="Type" rules={[{ required: true }]}>
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
  };


  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
      ...getColumnSearchProps('name'),
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
      sorter: (a, b) => a.method?.localeCompare(b.method),
      filters: [
        { text: 'Crystal', value: 'crystal' },
        { text: 'Shopify', value: 'shopify' },
        { text: 'F2F', value: 'f2f' },
        { text: 'Scrapper', value: 'scrapper' },
        { text: 'Other', value: 'other' },
      ],
      filteredValue: filteredInfo.method || null,
      onFilter: (value, record) => record.method === value,
    },
    {
      title: 'Country',
      dataIndex: 'country',
      key: 'country',
      sorter: (a, b) => a.country?.localeCompare(b.country),
      filters: getUniqueCountries(),
      filteredValue: filteredInfo.country || null,
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
      filteredValue: filteredInfo.type || null,
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
      ...getColumnSearchProps('url'),
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
      filteredValue: filteredInfo.active || null,
      onFilter: (value, record) => record.active === value,
      sorter: (a, b) => Number(a.active) - Number(b.active),
    },
    {
      title: (
        <div>
          Actions
          <Button
            size="small"
            style={{ marginLeft: 8 }}
            onClick={handleResetFilters}
          >
            Reset All Filters
          </Button>
        </div>
      ),
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
          onChange={(pagination, filters) => {
            setFilteredInfo(filters);
          }}
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