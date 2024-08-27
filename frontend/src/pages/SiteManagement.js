import React, { useState, useEffect, useContext } from 'react';
import { Table, Input, Button, Form, message, Switch, Modal } from 'antd';
import axios from 'axios';
import { SaveOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import ThemeContext from '../utils/ThemeContext';

const SiteManagement = () => {
  const [sites, setSites] = useState([]);
  const [isEditing, setIsEditing] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [addForm] = Form.useForm();
  const { isDarkMode } = useContext(ThemeContext);

  useEffect(() => {
    fetchSiteList();
  }, []);

  const fetchSiteList = async () => {
    try {
      const response = await axios.get('/api/v1/sites');
      setSites(response.data.map(item => ({ ...item, key: item.id })));
    } catch (error) {
      console.error('Error fetching site list:', error);
      message.error('Error fetching site list');
    }
  };

  const handleSave = async (id, data) => {
    try {
      await axios.put(`/api/v1/sites/${id}`, data);
      message.success('Site updated successfully');
    } catch (error) {
      console.error('Error updating site:', error);
      message.error('Error updating site');
    }
  };

  const handleAdd = async (data) => {
    try {
      const response = await axios.post('/api/v1/sites', data);
      setSites([...sites, { ...response.data, key: response.data.id }]);
      message.success('Site added successfully');
      setIsModalVisible(false);
    } catch (error) {
      console.error('Error adding site:', error);
      message.error('Error adding site');
    }
  };

  const saveAll = async () => {
    try {
      const rows = await form.validateFields();
      const updatedSites = sites.map(site => {
        const changes = rows[site.key] || {};
        return { ...site, ...changes };
      });
      setSites(updatedSites);
      for (const site of updatedSites) {
        if (modifiedSites[site.key]) {
          await handleSave(site.id, modifiedSites[site.key]);
        }
      }
      setIsEditing(false);
      setModifiedSites({});
    } catch (errInfo) {
      console.log('Validate Failed:', errInfo);
    }
  };

  const handleChange = (key, field, value) => {
    setModifiedSites(prev => ({
      ...prev,
      [key]: {
        ...prev[key],
        [field]: value,
      }
    }));
  };

  const handleSwitchChange = (key, checked) => {
    handleChange(key, 'active', checked);
  };

  const handleEditMode = () => {
    if (isEditing) {
      saveAll();
    } else {
      const initialValues = sites.reduce((acc, site) => {
        acc[site.key] = site;
        return acc;
      }, {});
      form.setFieldsValue(initialValues);
      setIsEditing(true);
    }
  };

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name', editable: true },
    { title: 'URL', dataIndex: 'url', key: 'url', editable: true },
    { title: 'Method', dataIndex: 'method', key: 'method', editable: true },
    { 
      title: 'Active', 
      dataIndex: 'active', 
      key: 'active', 
      editable: true,
      render: (_, record) => (
        <Switch checked={record.active} onChange={(checked) => handleSwitchChange(record.key, checked)} />
      )
    },
    { title: 'Country', dataIndex: 'country', key: 'country', editable: true },
    { title: 'Type', dataIndex: 'type', key: 'type', editable: true },
  ];

  const EditableCell = ({
    editing,
    dataIndex,
    title,
    record,
    children,
    ...restProps
  }) => {
    return (
      <td {...restProps}>
        {editing ? (
          <Form.Item
            name={[record.key, dataIndex]}
            style={{ margin: 0 }}
            rules={[{ required: true, message: `Please Input ${title}!` }]}
          >
            <Input onChange={(e) => handleChange(record.key, dataIndex, e.target.value)} />
          </Form.Item>
        ) : (
          children
        )}
      </td>
    );
  };

  const mergedColumns = columns.map((col) => {
    if (!col.editable) {
      return col;
    }
    return {
      ...col,
      onCell: (record) => ({
        record,
        dataIndex: col.dataIndex,
        title: col.title,
        editing: isEditing,
      }),
    };
  });

  const handleAddSite = () => {
    addForm.validateFields().then(values => {
      handleAdd(values);
      addForm.resetFields();
    }).catch(info => {
      console.log('Validate Failed:', info);
    });
  };

  return (
    <div className="site-management section">
      <h1>Site Management</h1>
      <Button
        type="primary"
        icon={isEditing ? <SaveOutlined /> : <EditOutlined />}
        onClick={handleEditMode}
      >
        {isEditing ? 'Save All' : 'Edit Mode'}
      </Button>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={() => setIsModalVisible(true)}
      >
        Add Site
      </Button>
      <Form form={form} component={false}>
        <Table
          components={{
            body: {
              cell: EditableCell,
            },
          }}
          bordered
          dataSource={sites}
          columns={mergedColumns}
          rowClassName="editable-row"
          pagination={false}
        />
      </Form>
      <Modal
        title="Add New Site"
        visible={isModalVisible}
        onOk={handleAddSite}
        onCancel={() => setIsModalVisible(false)}
      >
        <Form form={addForm} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Please input the site name!' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label="URL" rules={[{ required: true, message: 'Please input the site URL!' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="method" label="Method" rules={[{ required: true, message: 'Please input the site method!' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="country" label="Country" rules={[{ required: true, message: 'Please input the country!' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="Type" rules={[{ required: true, message: 'Please input the site type!' }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default SiteManagement;
