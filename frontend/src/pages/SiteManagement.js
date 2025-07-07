import React, { useState, useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient} from '@tanstack/react-query';
import { Card, Typography, Button, Space, Modal, Form, Input, message, Tag, Switch, Select } from 'antd';
import { EditOutlined, PlusOutlined, DeleteOutlined, ClearOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import { useSettings } from '../utils/SettingsContext';
import { useNotification } from '../utils/NotificationContext';
import { useApiWithNotifications } from '../utils/useApiWithNotifications';
import api from '../utils/api';
import { getColumnSearchProps } from '../utils/tableConfig';
import ColumnSelector from '../components/ColumnSelector';
import EnhancedTable from '../components/EnhancedTable';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';

const { Title } = Typography;
const { Option } = Select;

// Supported currencies for site configuration
const SUPPORTED_CURRENCIES = {
  'CAD': 'Canadian Dollar (C$)',
  'USD': 'US Dollar ($)',
  'EUR': 'Euro (€)',
  'GBP': 'British Pound (£)',
  'JPY': 'Japanese Yen (¥)',
  'AUD': 'Australian Dollar (A$)',
  'CHF': 'Swiss Franc (CHF)',
  'SEK': 'Swedish Krona (kr)',
  'NOK': 'Norwegian Krone (kr)',
  'DKK': 'Danish Krone (kr)',
};


const SiteManagement = () => {
  const { theme } = useTheme();
  const { settings } = useSettings(); 
  const queryClient = useQueryClient();
  const [editingRecord, setEditingRecord] = useState(null);
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [addForm] = Form.useForm();
  
  // Notification hooks
  const { messageApi, notificationApi } = useNotification();
  const { 
    createWithNotifications, 
    updateWithNotifications, 
    deleteWithNotifications 
  } = useApiWithNotifications();

  // Use enhanced table handler for consistent behavior
  const {
    filteredInfo,
    sortedInfo,
    pagination,
    selectedIds: selectedSiteIds,
    setSelectedIds: setSelectedSiteIds,
    searchInput,
    visibleColumns,
    handleTableChange,
    handleSearch,
    handleReset,
    handleResetAllFilters,
    handleColumnVisibilityChange
  } = useEnhancedTableHandler({
    visibleColumns: ['name', 'url', 'method', 'country', 'currency', 'type', 'active', 'action']
  }, 'site_management_table');

  const [editMethodValue, setEditMethodValue] = useState('');
  const [addMethodValue, setAddMethodValue] = useState('');
  // React Query to fetch sites
  const { data: sites = [], isLoading: loading } = useQuery({
    queryKey: ['sites'],
    queryFn: () => api.get('/sites').then(res => res.data),
    staleTime: 300000
  })
  
  // Mutation to add a site
  const addSiteMutation = useMutation({
    mutationFn: (values) => api.post('/sites', { ...values }),
    onSuccess: () => {
      queryClient.invalidateQueries(['sites']);
      notificationApi.success({
        message: 'Site created successfully',
        placement: 'topRight',
      });
      setIsAddModalVisible(false);
      addForm.resetFields();
    },
    onError: (error) => {
      console.error('Error adding site:', error);
      notificationApi.error({
        message: 'Failed to create site',
        description: error.message || 'Failed to add site',
        placement: 'topRight',
      });
    }
  });
  
  // Mutation to update a site
  const updateSiteMutation = useMutation({
    mutationFn: (values) => api.put(`/sites/${editingRecord.id}`, { ...values }),
    onSuccess: (response) => {
      if (!response.data) {
        showOperationError('update', 'No response data received', 'site');
        return;
      }
      switch (response.data.status) {
        case 'success':
          notificationApi.success({
            message: 'Site updated successfully',
            placement: 'topRight',
          });
          
          queryClient.invalidateQueries(['sites']);
          setIsEditModalVisible(false);
          break;
          case 'info':
            notificationApi.info({
              message: 'Site updated',
              description: response.data.message || 'Site updated with some considerations',
              placement: 'topRight',
            });
            setIsEditModalVisible(false);
            break;
          case 'warning':
            notificationApi.warning({
              message: 'Site updated with warnings',
              description: response.data.message || 'Site updated with warnings',
              placement: 'topRight',
            });
          break;
          default:
            showOperationError('update', 'Unknown status returned', 'site');
      }
    },
    onError: (error) => {
      console.error('Error updating site:', error);
      showOperationError('update', error.message || 'Failed to update site', 'site');
    }
  });
  
  // Mutation to delete a site
  const deleteSiteMutation = useMutation({
    mutationFn: (id) => api.delete(`/sites/${id}`),
    // Optimistic update - remove the item immediately from UI
    onMutate: async (siteId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries(['sites']);
      
      // Save the previous value
      const previousSites = queryClient.getQueryData(['sites']);
      
      // Optimistically update to the new value
      queryClient.setQueryData(['sites'], old => 
        old.filter(site => site.id !== siteId)
      );
      
      // Return the previous value in case of rollback
      return { previousSites };
    },
    onError: (err, siteId, context) => {
      // Roll back to the previous value if there's an error
      queryClient.setQueryData(['sites'], context.previousSites);
      showOperationError('delete', err.message || 'Failed to delete site', 'site');
    },
    onSuccess: () => {
      showOperationSuccess('delete', 'site');
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries(['sites']);
    }
  });
  
  
  const handleEdit = useCallback((record, e) => {
    if (e) e.stopPropagation();
    setEditingRecord(record);
    setEditMethodValue(record.method || '');
    editForm.setFieldsValue(record);
    setIsEditModalVisible(true);
  }, [editForm]);

  const handleAdd = useCallback(() => {
    addForm.resetFields();
    setIsAddModalVisible(true);
  }, [addForm]);
  
  const handleEditSubmit = useCallback(async () => {
    try {
      const values = await editForm.validateFields();
      updateSiteMutation.mutate(values);
    } catch (error) {
      console.error('Form validation error:', error);
    }
  }, [editForm, updateSiteMutation]);
  
  const handleAddSubmit = useCallback(async () => {
    try {
      const values = await addForm.validateFields();
      addSiteMutation.mutate(values);
    } catch (error) {
      console.error('Form validation error:', error);
    }
  }, [addForm, addSiteMutation]);
  
  const handleDelete = useCallback((id, e) => {
    if (e) e.stopPropagation();
    deleteSiteMutation.mutate(id);
  }, [deleteSiteMutation]);
  
  const handleBulkDelete = useCallback(async () => {
    if (selectedSiteIds.size === 0) {
      messageApi.warning('No sites selected for deletion.');
      return;
    }
  
    await deleteWithNotifications(
      async () => {
        const siteIdList = Array.from(selectedSiteIds);
        await api.delete('/sites/delete-many', {
          data: { site_ids: siteIdList }
        });
        return { count: siteIdList.length };
      },
      'site(s)',
      {
        loadingMessage: `Deleting ${selectedSiteIds.size} site(s)...`,
        onSuccess: () => {
          setSelectedSiteIds(new Set());
          queryClient.invalidateQueries(['sites']);
        }
      }
    );
  }, [selectedSiteIds, deleteWithNotifications, setSelectedSiteIds, queryClient]);
  

  const handleMethodChange = useCallback((value, formType) => {
    if (formType === 'edit') {
      setEditMethodValue(value);
    } else {
      setAddMethodValue(value);
    }
  }, []);

  // Column definitions for the sites table
  const siteColumns = useMemo(() => [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
      sortOrder: sortedInfo.columnKey === 'name' && sortedInfo.order,
      ...getColumnSearchProps('name', searchInput, filteredInfo, 'Search name', handleSearch, handleReset),
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
      ...getColumnSearchProps('url', searchInput, filteredInfo, 'Search URL', handleSearch, handleReset),
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
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
      filters: [
        { text: 'USA', value: 'USA' },
        { text: 'Canada', value: 'Canada' },
        { text: 'Others', value: 'Others' },
      ],
      filteredValue: filteredInfo.country || null,
      onFilter: (value, record) => record.country === value,
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      filters: [
        { text: 'Primary', value: 'Primary' },
        { text: 'Extended', value: 'Extended' },
        { text: 'Marketplace', value: 'Marketplace' },
        { text: 'No Inventory', value: 'NoInventory' },
        { text: 'Not Working', value: 'NotWorking' },
      ],
      filteredValue: filteredInfo.type || null,
      onFilter: (value, record) => record.type === value,
    },
    {
      title: 'Currency',
      dataIndex: 'currency',
      key: 'currency',
      render: (currency) => {
        const currencyInfo = SUPPORTED_CURRENCIES[currency] || currency;
        const isSupported = SUPPORTED_CURRENCIES[currency];
        return (
          <Tag color={isSupported ? "blue" : "orange"} title={currencyInfo}>
            {currency}
          </Tag>
        );
      },
      filters: Object.keys(SUPPORTED_CURRENCIES).map(code => ({
        text: `${code} - ${SUPPORTED_CURRENCIES[code]}`,
        value: code,
      })),
      filteredValue: filteredInfo.currency || null,
      onFilter: (value, record) => record.currency === value,
    },
    {
      title: 'Active',
      dataIndex: 'active',
      key: 'active',
      render: (active) => active ? <Tag color="green">Yes</Tag> : <Tag color="red">No</Tag>,
      filters: [
        { text: 'Active', value: true },
        { text: 'Inactive', value: false },
      ],
      filteredValue: filteredInfo.active || null,
      onFilter: (value, record) => record.active === value,
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={(e) => { e.stopPropagation(); handleEdit(record, e); }}>
            Edit
          </Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={(e) => { e.stopPropagation(); handleDelete(record.id, e); }}>
            Delete
          </Button>
        </Space>
      )
    }
  ], [filteredInfo, sortedInfo, handleSearch, handleReset, handleEdit, handleDelete]);
  
  return (
    <div className={`site-management ${theme}`}>
      <Title level={2}>Site Management</Title>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<PlusOutlined />} onClick={handleAdd}>
          Add Site
        </Button>
        <ColumnSelector 
          columns={siteColumns}
          visibleColumns={visibleColumns}
          onColumnToggle={handleColumnVisibilityChange}
          persistKey="site_management_columns"
        />
        <Button icon={<ClearOutlined />} onClick={handleResetAllFilters}>
          Reset All Filters
        </Button>
        {selectedSiteIds.size > 0 && (
          <Button danger onClick={handleBulkDelete} icon={<DeleteOutlined />}>
            Delete Selected ({selectedSiteIds.size})
          </Button>
        )}
      </Space>
      
      <EnhancedTable
        dataSource={sites}
        columns={siteColumns.filter(col => visibleColumns.includes(col.key))}
        exportFilename="sites_export"
        exportCopyFormat={null}
        rowKey="id"
        loading={loading}
        persistStateKey="site_management_table"
        rowSelectionEnabled={true}
        selectedIds={selectedSiteIds}
        onSelectionChange={setSelectedSiteIds}
        onChange={handleTableChange}
        pagination={pagination} 
      />
      
      {/* Edit Modal */}
      <Modal
        title="Edit Site"
        open={isEditModalVisible}
        onCancel={() => setIsEditModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsEditModalVisible(false)}>
            Cancel
          </Button>,
          <Button key="submit" type="primary" onClick={handleEditSubmit}>
            Save
          </Button>
        ]}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Please enter a site name' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label="URL" rules={[{ required: true, type: 'url', message: 'Please enter a valid URL' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="method" label="Method" rules={[{ required: true, message: 'Please select a method' }]}>
            <Select>
              <Option value="crystal">Crystal</Option>
              <Option value="shopify">Shopify</Option>
              <Option value="f2f">F2F</Option>
              <Option value="scrapper">Scrapper</Option>
              <Option value="other">Other</Option>
            </Select>
          </Form.Item>
          {isEditModalVisible && (editForm.getFieldValue('method') === 'shopify' || editForm.getFieldValue('method') === 'f2f') && (
            <Form.Item
              name="api_url"
              label="API URL"
              rules={[{ required: true, message: 'API URL is required for this method' }]}
            >
              <Input />
            </Form.Item>
          )}
          <Form.Item name="country" label="Country" rules={[{ required: true, message: 'Please select a country' }]}>
            <Select>
              <Option value="USA">USA</Option>
              <Option value="Canada">Canada</Option>
              <Option value="Others">Others</Option>
            </Select>
          </Form.Item>
          <Form.Item name="type" label="Type" rules={[{ required: true, message: 'Please select a type' }]}>
            <Select>
              <Option value="Primary">Primary</Option>
              <Option value="Extended">Extended</Option>
              <Option value="Marketplace">Marketplace</Option>
              <Option value="NoInventory">No Inventory</Option>
              <Option value="NotWorking">Not Working</Option>
            </Select>
          </Form.Item>
          <Form.Item name="currency" label="Currency" rules={[{ required: true, message: 'Please select a currency' }]}>
            <Select placeholder="Select currency" showSearch optionFilterProp="children">
              {Object.entries(SUPPORTED_CURRENCIES).map(([code, name]) => (
                <Option key={code} value={code} title={name}>
                  <span style={{ fontWeight: 'bold' }}>{code}</span> - {name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
      
      {/* Add Modal */}
      <Modal
        title="Add Site"
        open={isAddModalVisible}
        onCancel={() => setIsAddModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsAddModalVisible(false)}>
            Cancel
          </Button>,
          <Button key="submit" type="primary" onClick={handleAddSubmit}>
            Add
          </Button>
        ]}
      >
        <Form form={addForm} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Please enter a site name' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label="URL" rules={[{ required: true, type: 'url', message: 'Please enter a valid URL' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="method" label="Method" rules={[{ required: true, message: 'Please select a method' }]}>
            <Select>
              <Option value="crystal">Crystal</Option>
              <Option value="shopify">Shopify</Option>
              <Option value="f2f">F2F</Option>
              <Option value="scrapper">Scrapper</Option>
              <Option value="other">Other</Option>
            </Select>
          </Form.Item>
          {isAddModalVisible && (addForm.getFieldValue('method') === 'shopify' || addForm.getFieldValue('method') === 'f2f') && (
            <Form.Item
              name="api_url"
              label="API URL"
              rules={[{ required: true, message: 'API URL is required for this method' }]}
            >
              <Input />
            </Form.Item>
          )}
          <Form.Item name="country" label="Country" rules={[{ required: true, message: 'Please select a country' }]}>
            <Select>
              <Option value="USA">USA</Option>
              <Option value="Canada">Canada</Option>
              <Option value="Others">Others</Option>
            </Select>
          </Form.Item>
          <Form.Item name="type" label="Type" rules={[{ required: true, message: 'Please select a type' }]}>
            <Select>
              <Option value="Primary">Primary</Option>
              <Option value="Extended">Extended</Option>
              <Option value="Marketplace">Marketplace</Option>
              <Option value="NoInventory">No Inventory</Option>
              <Option value="NotWorking">Not Working</Option>
            </Select>
          </Form.Item>
          <Form.Item name="currency" label="Currency" rules={[{ required: true, message: 'Please select a currency' }]} initialValue="CAD">
            <Select placeholder="Select currency" showSearch optionFilterProp="children">
              {Object.entries(SUPPORTED_CURRENCIES).map(([code, name]) => (
                <Option key={code} value={code} title={name}>
                  <span style={{ fontWeight: 'bold' }}>{code}</span> - {name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default SiteManagement;