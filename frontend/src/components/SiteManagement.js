import React, { useState, useEffect } from 'react';
import { Table, Input, Button, Form, message } from 'antd';
import { SaveOutlined, EditOutlined } from '@ant-design/icons';

const SiteManagement = () => {
  const [sites, setSites] = useState([]);
  const [isEditing, setIsEditing] = useState(false);
  const [modifiedSites, setModifiedSites] = useState({});
  const [form] = Form.useForm();

  useEffect(() => {
    fetchSiteList();
  }, []);

  const fetchSiteList = async () => {
    try {
      const response = await fetch('/get_site_list');
      if (response.ok) {
        const data = await response.json();
        setSites(data.map(item => ({ ...item, key: item.id })));
      } else {
        message.error('Failed to fetch site list');
      }
    } catch (error) {
      console.error('Error fetching site list:', error);
      message.error('Error fetching site list');
    }
  };

  const handleSave = async (id, data) => {
    try {
      const response = await fetch(`/update_site/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (response.ok) {
        message.success('Site updated successfully');
      } else {
        message.error('Failed to update site');
      }
    } catch (error) {
      console.error('Error updating site:', error);
      message.error('Error updating site');
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

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name', editable: true },
    { title: 'URL', dataIndex: 'url', key: 'url', editable: true },
    { title: 'Parse Method', dataIndex: 'parse_method', key: 'parse_method', editable: true },
    { title: 'Type', dataIndex: 'type', key: 'type', editable: true },
  ];

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

  const handleEditMode = () => {
    if (isEditing) {
      saveAll();
    } else {
      // Set initial form values
      const initialValues = sites.reduce((acc, site) => {
        acc[site.key] = site;
        return acc;
      }, {});
      form.setFieldsValue(initialValues);
      setIsEditing(true);
    }
  };

  return (
    <div>
      <h1>Site Management</h1>
      <Button
        type="primary"
        icon={isEditing ? <SaveOutlined /> : <EditOutlined />}
        onClick={handleEditMode}
      >
        {isEditing ? 'Save All' : 'Edit Mode'}
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
    </div>
  );
};

export default SiteManagement;
