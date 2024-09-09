import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, message, Spin, Space, Popconfirm, Form, Input, Select } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import CardListInput from '../components/CardManagement/CardListInput';
import axios from 'axios';
import ScryfallCard from '../components/CardManagement/ScryfallCard';

const { Option } = Select;

const CardManagement = () => {
  const [cards, setCards] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [form] = Form.useForm();
  const [sets, setSets] = useState([]);
  const [languages, setLanguages] = useState([]);
  const [versions, setVersions] = useState([]);

  useEffect(() => {
    fetchCards();
    fetchSets();
  }, []);

  const fetchCards = async () => {
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/cards`);
      setCards(response.data);
    } catch (error) {
      message.error('Failed to fetch cards');
    }
  };

  const fetchSets = async () => {
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/sets`);
      setSets(response.data);
    } catch (error) {
      message.error('Failed to fetch sets');
    }
  };

  const handleCardClick = async (card) => {
    setSelectedCard(card);
    setIsLoading(true);
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/fetch_card`, {
        params: {
          name: card.name,
          set: card.set,
          language: card.language,
          version: card.version
        }
      });
      
      if (response.data.error) {
        throw new Error(response.data.error);
      }
      
      console.log('Card data:', response.data);
      setCardData(response.data);
      setIsModalVisible(true);

      // Update languages and versions based on the fetched data
      if (response.data.scryfall) {
        setLanguages(response.data.scryfall.languages || []);
        setVersions(response.data.scryfall.versions || []);
      }
    } catch (error) {
      console.error('Error fetching card data:', error);
      message.error(`Failed to fetch card data: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
    setSelectedCard(null);
    setCardData(null);
  };

  const handleEditClick = (card) => {
    setSelectedCard(card);
    form.setFieldsValue(card);
    setIsEditModalVisible(true);
  };

  const handleEditModalClose = () => {
    setIsEditModalVisible(false);
    setSelectedCard(null);
    form.resetFields();
  };

  const handleEditSubmit = async () => {
    try {
      const values = await form.validateFields();
      await axios.put(`${process.env.REACT_APP_API_URL}/cards/${selectedCard.id}`, values);
      message.success('Card updated successfully');
      handleEditModalClose();
      fetchCards();
    } catch (error) {
      console.error('Failed to update card:', error);
      message.error('Failed to update card');
    }
  };

  const handleDelete = async (cardId) => {
    try {
      await axios.delete(`${process.env.REACT_APP_API_URL}/cards/${cardId}`);
      message.success('Card deleted successfully');
      fetchCards();
    } catch (error) {
      console.error('Failed to delete card:', error);
      message.error('Failed to delete card');
    }
  };

  const handleCardListSubmit = async (cardList) => {
    try {
      await axios.post(`${process.env.REACT_APP_API_URL}/cards`, cardList);
      message.success('Card list updated successfully');
      fetchCards();
    } catch (error) {
      message.error('Failed to update card list');
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Quantity',
      dataIndex: 'quantity',
      key: 'quantity',
    },
    {
      title: 'Set',
      dataIndex: 'set',
      key: 'set',
    },
    {
      title: 'Language',
      dataIndex: 'language',
      key: 'language',
    },
    {
      title: 'Version',
      dataIndex: 'version',
      key: 'version',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (text, record) => (
        <Space>
          <Button icon={<EyeOutlined />} onClick={() => handleCardClick(record)}>View</Button>
          <Button icon={<EditOutlined />} onClick={() => handleEditClick(record)}>Edit</Button>
          <Popconfirm
            title="Are you sure you want to delete this card?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button icon={<DeleteOutlined />} danger>Delete</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="card-management">
      <h1>Card Management</h1>
      <CardListInput onSubmit={handleCardListSubmit} />
      <Table dataSource={cards} columns={columns} rowKey="id" />
      <Modal
        title={selectedCard ? selectedCard.name : ''}
        open={isModalVisible}
        onCancel={handleModalClose}
        width={800}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Close
          </Button>
        ]}
      >
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin size="large" />
            <p>Loading card data...</p>
          </div>
        ) : cardData ? (
          <ScryfallCard data={cardData.scryfall} />
        ) : null}
      </Modal>
      <Modal
        title={`Edit ${selectedCard ? selectedCard.name : ''}`}
        open={isEditModalVisible}
        onCancel={handleEditModalClose}
        onOk={handleEditSubmit}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="set" label="Set" rules={[{ required: true }]}>
            <Select>
              {sets.map(set => (
                <Option key={set.code} value={set.code}>{set.name}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="quantity" label="Quantity" rules={[{ required: true, type: 'number', min: 1 }]}>
            <Input type="number" />
          </Form.Item>
          <Form.Item name="language" label="Language" rules={[{ required: true }]}>
            <Select>
              {languages.map(lang => (
                <Option key={lang} value={lang}>{lang}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="version" label="Version" rules={[{ required: true }]}>
            <Select>
              {versions.map(ver => (
                <Option key={ver} value={ver}>{ver}</Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default CardManagement;