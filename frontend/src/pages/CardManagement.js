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
      message.error('Failed to fetch user buylist');
    }
  };

  const handleCardClick = async (card) => {

    console.log('Card clicked:', card);

    if (!card.name) {
      message.error('Card name is missing');
      return;
    }

    setSelectedCard(card);
    setIsLoading(true);

    // Construct the query parameters for Scryfall API
    let query = `fuzzy=${encodeURIComponent(card.name)}`;
    if (card.set) {
      query += `&set=${encodeURIComponent(card.set)}`;
    }
    if (card.language) {
      query += `&lang=${encodeURIComponent(card.language)}`;
    }
    console.log('Scryfall API query:', query);  // Log the query

    // Fetch card details from Scryfall API
    try {
      const response = await fetch(`${SCRYFALL_API_BASE}/cards/named?${query}`);
      const scryfallData = await response.json();

      console.log('Scryfall data:', scryfallData);  // Log the fetched data
      
      if (scryfallData.status === 404) {
        throw new Error('Card not found');
      }
      setCardData(scryfallData);
      setIsModalVisible(true);
    } catch (error) {
      message.error(`Failed to fetch card details: ${error.message}`);
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
          <Spin size="large" />
        ) : cardData ? (
          <ScryfallCard card={cardData} onSetClick={handleSetClick} />
        ) : <div>No card data available</div>}
      </Modal>
    </div>
  );
};

const handleSetClick = async (setCode) => {
  try {
    console.log('Set clicked:', setCode);  // Log the clicked set
    await api.post('/save_set_selection', { set: setCode });
    message.success('Set selection saved successfully');
  } catch (error) {
    message.error(`Failed to save set: ${error.message}`);
  }
};

export default CardManagement;
