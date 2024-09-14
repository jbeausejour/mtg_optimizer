import React, { useState, useEffect } from 'react';
import { Table, Input, Button, Modal, message, Spin, Space, Popconfirm, Form, Select, Tooltip, Image } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined, SearchOutlined } from '@ant-design/icons';
import CardListInput from '../components/CardManagement/CardListInput';
import ScryfallCard from '../components/CardManagement/ScryfallCard';
import api from '../utils/api';


const SCRYFALL_API_BASE = "https://api.scryfall.com";
const CardManagement = () => {
  const [cards, setCards] = useState([]);
  const [filteredCards, setFilteredCards] = useState([]);
  const [searchText, setSearchText] = useState('');
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchCards();
  }, []);

  const fetchCards = async () => {
    try {
      const response = await api.get('/cards');
      setCards(response.data);
      setFilteredCards(response.data);  // Initialize the filtered list
    } catch (error) {
      message.error('Failed to fetch cards');
    }
  };

  const handleCardClick = async (card) => {
    setSelectedCard(card);
    setIsLoading(true);
    try {
      const response = await api.get('/fetch_card', {
        params: {
          name: card.name,
          set: card.set,
          language: card.language,
          version: card.version
        }
      });
      setCardData(response.data);
      setIsModalVisible(true);
    } catch (error) {
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

  const onSearch = (value) => {
    setSearchText(value);
    const filtered = cards.filter((card) =>
      card.name && card.name.toLowerCase().includes(value.toLowerCase())  // Ensure card.name exists
    );
    setFilteredCards(filtered);
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      filterDropdown: () => (
        <div style={{ padding: 8 }}>
          <Input
            placeholder="Search name"
            value={searchText}
            onChange={(e) => onSearch(e.target.value)}
            style={{ width: 188, marginBottom: 8, display: 'block' }}
            prefix={<SearchOutlined />}
          />
        </div>
      ),
      filterIcon: <SearchOutlined />,
      render: (text, record) => (
        <Tooltip
          title={
            record.name && record.set ? (
              <Image
                src={`${SCRYFALL_API_BASE}/cards/named?exact=${record.name}`}
                alt={record.name}
                style={{ width: '150px' }}  // Adjust the image size as needed
              />
            ) : 'No Image Available'
          }
        >
          {record.name ? (
            <a href="#" style={{ textDecoration: 'underline', color: 'blue' }}>
              {text}
            </a>
          ) : 'Unknown Name'}
        </Tooltip>
      ),      
    },
    {
      title: 'Quantity',
      dataIndex: 'quantity',
      key: 'quantity',
      sorter: (a, b) => a.quantity - b.quantity,
    },
    {
      title: 'Set',
      dataIndex: 'set',
      key: 'set',
      sorter: (a, b) => a.set.localeCompare(b.set),
    },
    {
      title: 'Language',
      dataIndex: 'language',
      key: 'language',
      sorter: (a, b) => a.language.localeCompare(b.language),
    },
    {
      title: 'Version',
      dataIndex: 'version',
      key: 'version',
      sorter: (a, b) => a.version.localeCompare(b.version),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (text, record) => (
        <Space>
          <Button icon={<EyeOutlined />} onClick={() => handleCardClick(record)}>View</Button>
          <Button icon={<EditOutlined />}>Edit</Button>
          <Popconfirm
            title="Are you sure you want to delete this card?"
            onConfirm={() => message.success('Card deleted')}  // Implement delete logic here
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
      <CardListInput />
      <Table dataSource={filteredCards} columns={columns} rowKey="id" pagination={false} />
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
    </div>
  );
};

export default CardManagement;
