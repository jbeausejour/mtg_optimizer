import React, { useState, useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient} from '@tanstack/react-query';
import { Card, Typography, Button, Space, Modal, Form, Input, message, Spin, Tag, Switch, Select } from 'antd';
import { EditOutlined, PlusOutlined, DeleteOutlined, SearchOutlined, ClearOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import api from '../utils/api';
import { getColumnSearchProps } from '../utils/tableConfig';
import ColumnSelector from '../components/ColumnSelector';
import EnhancedTable from '../components/EnhancedTable';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';

const { Title } = Typography;
const { Option } = Select;

const SiteManagement = ({ userId }) => {
  const { theme } = useTheme();
  const queryClient = useQueryClient();
  const [editingRecord, setEditingRecord] = useState(null);
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [addForm] = Form.useForm();
  
  // Use enhanced table handler for consistent behavior
  const {
    filteredInfo,
    sortedInfo,
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
    visibleColumns: ['name', 'url', 'method', 'country', 'type', 'active', 'action']
  }, 'site_management_table');

  const [editMethodValue, setEditMethodValue] = useState('');
  const [addMethodValue, setAddMethodValue] = useState('');
  // React Query to fetch sites
  const { data: sites = [], isLoading: loading } = useQuery({
    queryKey: ['sites', userId],
    queryFn: () => api.get('/sites', { params: { user_id: userId } }).then(res => res.data),
    staleTime: 300000
  })
  
  // Mutation to add a site
  const addSiteMutation = useMutation({
    mutationFn: (values) => api.post('/sites', { ...values, user_id: userId }),
    onSuccess: () => {
      queryClient.invalidateQueries(['sites', userId]);
      message.success('Site added successfully');
      setIsAddModalVisible(false);
      addForm.resetFields();
    },
    onError: (error) => {
      console.error('Error adding site:', error);
      message.error('Failed to add site');
    }
  });
  
  // Mutation to update a site
  const updateSiteMutation = useMutation({
    mutationFn: (values) => api.put(`/sites/${editingRecord.id}`, { ...values, user_id: userId }),
    onSuccess: (response) => {
      if (!response.data) {
        message.error('Failed to update site: No response data');
        return;
      }
      switch (response.data.status) {
        case 'success':
          message.success(response.data.message || 'Site updated successfully');
          queryClient.invalidateQueries(['sites', userId]);
          setIsEditModalVisible(false);
          break;
        case 'info':
          message.info(response.data.message || 'Site updated with some considerations');
          setIsEditModalVisible(false);
          break;
        case 'warning':
          message.warning(response.data.message || 'Site updated with warnings');
          break;
        default:
          message.error('Failed to update site: Unknown status');
      }
    },
    onError: (error) => {
      console.error('Error updating site:', error);
      message.error('Failed to update site');
    }
  });
  
  // Mutation to delete a site
  const deleteSiteMutation = useMutation({
    mutationFn: (id) => api.delete(`/sites/${id}`, { params: { user_id: userId } }),
    // Optimistic update - remove the item immediately from UI
    onMutate: async (siteId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries(['sites', userId]);
      
      // Save the previous value
      const previousSites = queryClient.getQueryData(['sites', userId]);
      
      // Optimistically update to the new value
      queryClient.setQueryData(['sites', userId], old => 
        old.filter(site => site.id !== siteId)
      );
      
      // Return the previous value in case of rollback
      return { previousSites };
    },
    onError: (err, siteId, context) => {
      // Roll back to the previous value if there's an error
      queryClient.setQueryData(['sites', userId], context.previousSites);
      message.error('Failed to delete site.');
    },
    onSuccess: () => {
      message.success('Site deleted successfully');
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries(['sites', userId]);
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
  
  // Handle bulk deletion
  const handleBulkDelete = useCallback(() => {
    if (selectedSiteIds.size === 0) {
      message.warning('No sites selected for deletion.');
      return;
    }
    
    Modal.confirm({
      title: `Are you sure you want to delete ${selectedSiteIds.size} selected site(s)?`,
      content: 'This action cannot be undone.',
      okText: 'Yes, delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          // Store count before clearing for message
          const count = selectedSiteIds.size;
          
          // Create an array of deletion promises
          const deletionPromises = Array.from(selectedSiteIds).map(id => 
            deleteSiteMutation.mutateAsync(id)
          );
          
          // Wait for all deletions to complete
          await Promise.all(deletionPromises);
          
          // Clear selection and show success
          setSelectedSiteIds(new Set());
          message.success(`Successfully deleted ${count} site(s).`);
          
          // Invalidate after everything is done
          queryClient.invalidateQueries(['sites', userId]);
        } catch (error) {
          console.error('Bulk deletion error:', error);
          message.error('Failed to delete some or all selected sites.');
          // Invalidate to get back to a consistent state
          queryClient.invalidateQueries(['sites', userId]);
        }
      }
    });
  }, [selectedSiteIds, deleteSiteMutation, setSelectedSiteIds, userId]);

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
        rowKey="id"
        loading={loading}
        persistStateKey="site_management_table"
        rowSelectionEnabled={true}
        selectedIds={selectedSiteIds}
        onSelectionChange={setSelectedSiteIds}
        onRowClick={() => {}}
        onChange={handleTableChange}
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
          {(editForm.getFieldValue('method') === 'shopify' || editForm.getFieldValue('method') === 'f2f') && (
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
          {(addForm.getFieldValue('method') === 'shopify' || addForm.getFieldValue('method') === 'f2f') && (
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
          <Form.Item name="active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default SiteManagement;