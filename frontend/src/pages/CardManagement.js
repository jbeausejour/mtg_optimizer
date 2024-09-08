import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, message } from 'antd';
import CardListInput from '../components/CardManagement/CardListInput';
import CardSearchAndDetails from '../components/CardManagement/CardSearchAndDetails';
import axios from 'axios';

const CardManagement = () => {
  const [cards, setCards] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);

  useEffect(() => {
    fetchCards();
  }, []);

  const fetchCards = async () => {
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/cards`);
      setCards(response.data);
    } catch (error) {
      message.error('Failed to fetch cards');
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
      title: 'Actions',
      key: 'actions',
      render: (text, record) => (
        <Button onClick={() => handleCardClick(record)}>View Details</Button>
      ),
    },
  ];

  const handleCardClick = (card) => {
    setSelectedCard(card);
    setIsModalVisible(true);
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
    setSelectedCard(null);
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

  return (
    <div className="card-management">
      <h1>Card Management</h1>
      <CardListInput onSubmit={handleCardListSubmit} />
      <Table dataSource={cards} columns={columns} rowKey="id" />
      <Modal
        title="Card Details"
        open={isModalVisible}
        onCancel={handleModalClose}
        footer={null}
        width={800}
      >
        {selectedCard && <CardSearchAndDetails cardName={selectedCard.name} />}
      </Modal>
    </div>
  );
};

export default CardManagement;