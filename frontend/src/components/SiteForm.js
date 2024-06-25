import React, { useState, useEffect } from 'react';
import { Form, Input, Button } from 'antd';

const SiteForm = ({ handleClose, handleSave, editSite }) => {
  const [form] = Form.useForm();
  const [site, setSite] = useState({ name: '', url: '', parse_method: '', type: '' });

  useEffect(() => {
    if (editSite) {
      setSite(editSite);
      form.setFieldsValue(editSite);
    } else {
      setSite({ name: '', url: '', parse_method: '', type: '' });
      form.resetFields();
    }
  }, [editSite, form]);

  const onFinish = (values) => {
    handleSave(editSite ? editSite.id : null, values);
  };

  return (
    <Form form={form} layout="vertical" onFinish={onFinish}>
      <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Please input the site name!' }]}>
        <Input />
      </Form.Item>
      <Form.Item name="url" label="URL" rules={[{ required: true, message: 'Please input the site URL!' }]}>
        <Input />
      </Form.Item>
      <Form.Item name="parse_method" label="Parse Method" rules={[{ required: true, message: 'Please input the parse method!' }]}>
        <Input />
      </Form.Item>
      <Form.Item name="type" label="Type" rules={[{ required: true, message: 'Please input the site type!' }]}>
        <Input />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit">
          {editSite ? 'Update Site' : 'Add Site'}
        </Button>
        <Button type="default" onClick={handleClose} style={{ marginLeft: '8px' }}>
          Cancel
        </Button>
      </Form.Item>
    </Form>
  );
};

export default SiteForm;
