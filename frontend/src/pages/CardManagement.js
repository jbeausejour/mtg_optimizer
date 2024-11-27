import React, { useState, useEffect } from 'react';
import { Table, Input, Button, Modal, message, Spin, Space, Popconfirm, Form, List, Tooltip, Image } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined, SearchOutlined } from '@ant-design/icons';
import CardListInput from '../components/CardManagement/CardListInput';
import { useTheme } from '../utils/ThemeContext';
import ScryfallCard from '../components/CardManagement/ScryfallCard';
import api from '../utils/api';

const SCRYFALL_API_BASE = "https://api.scryfall.com";

const CardManagement = () => {
  const [cards, setCards] = useState([]);
  const [filteredCards, setFilteredCards] = useState([]);
  const [searchText, setSearchText] = useState('');
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [modalMode, setModalMode] = useState('view'); // "view" or "edit"
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [form] = Form.useForm();
  const { theme } = useTheme();

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

  const fetchCardData = async (card) => {
    try {
      const response = await api.get(`/fetch_card?name=${card.name}`);
      if (response.data.error) throw new Error(response.data.error);
      return response.data;
    } catch (error) {
      message.error(`Failed to fetch card data: ${error.message}`);
      throw error; // Rethrow for further handling
    }
  };
  
  const handleViewCard = async (card) => {
    console.log('ViewCard clicked:', card); // Debug log
    setModalMode('view'); // Set mode explicitly
    setSelectedCard(card); // Set selected card
    setIsLoading(true);
  
    try {
      const data = await fetchCardData(card); // Fetch card data
      setCardData(data); // Update card data
      setIsModalVisible(true); // Open modal
    } catch (error) {
      console.error('Error fetching card data:', error);
      message.error(`Failed to fetch card data: ${error.message}`);
    } finally {
      setIsLoading(false); // Stop spinner
    }
  };
  
  const handleEditCard = async (card) => {
    console.log('EditCard clicked:', card); // Debug log
    setModalMode('edit'); // Set mode explicitly
    setSelectedCard(card); // Set selected card
    setIsLoading(true);
  
    try {
      const data = await fetchCardData(card); // Fetch card data
      setCardData(data); // Update card data
      setIsModalVisible(true); // Open modal
    } catch (error) {
      console.error('Error fetching card data:', error);
      message.error(`Failed to fetch card data: ${error.message}`);
    } finally {
      setIsLoading(false); // Stop spinner
    }
  };
  
  const handleModalClose = () => {
    console.log('Modal closed'); // Debug log
    setIsModalVisible(false); // Close modal
    setSelectedCard(null); // Clear selected card
    setCardData(null); // Clear card data
    setTimeout(() => setModalMode('view'), 0); // Reset mode to "view"
  };

  const handleSaveEdit = async (selectedPrinting) => {
    if (!selectedCard || !selectedPrinting) {
      message.error('No card or printing selected');
      return;
    }
  
    const updatedCard = {
      id: selectedCard.id,
      name: selectedPrinting.name,         // Changed from 'Name'
      set_name: selectedPrinting.set,      // Changed from 'Edition'
      language: selectedPrinting.lang || selectedCard.language,  // Already lowercase
      quantity: selectedCard.quantity,      // Already lowercase
      version: selectedPrinting.version || selectedCard.version, // Already lowercase
      foil: selectedCard.foil              // Already lowercase
    };
  
    try {
      const response = await api.put(`/cards/${selectedCard.id}`, updatedCard, {
        headers: {
          'Content-Type': 'application/json',
        },
      });
  
      const updatedCardData = response.data;
  
      // Update the local state with the updated card
      setCards((prevCards) =>
        prevCards.map((card) =>
          card.id === updatedCardData.id ? updatedCardData : card
        )
      );
      setFilteredCards((prevCards) =>
        prevCards.map((card) =>
          card.id === updatedCardData.id ? updatedCardData : card
        )
      );
  
      message.success('Card updated successfully');
      handleModalClose();
    } catch (error) {
      console.error('Error updating card:', error);
      message.error(`Failed to update card: ${error.message}`);
    }
  };

  const handleDeleteCard = async (cardId) => {
    try {
      await api.delete(`/cards/${cardId}`);
      message.success('Card deleted successfully');
      setCards((prev) => prev.filter((card) => card.id !== cardId));
      setFilteredCards((prev) => prev.filter((card) => card.id !== cardId));
    } catch (error) {
      message.error(`Failed to delete card: ${error.message}`);
    }
  };

  const onSearch = (value) => {
    setSearchText(value);
    const filtered = cards.filter((card) =>
      card.name && card.name.toLowerCase().includes(value.toLowerCase())  // Ensure card.name exists
    );
    setFilteredCards(filtered);
  };
  
  return (
    console.log('isEditMode:', modalMode),
    <div className="card-management">
      <h1>Card Management</h1>
      {/* Search Input */}
      <Input
        placeholder="Search cards..."
        value={searchText}
        onChange={(e) => handleSearch(e.target.value)}
        style={{ marginBottom: 16 }}
      />

      {/* List with Columns */}
      <List
        bordered
        dataSource={filteredCards}
        renderItem={(card) => (
          <List.Item
            className={`list-item custom-hover-row ${theme}`} 
            onClick={() => handleViewCard(card)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
              {/* Card Name */}
              <div style={{ flex: 2 }}>
                {card.name}
              </div>

              {/* Quantity */}
              <div style={{ flex: 1, textAlign: 'center' }}>{card.quantity}</div>

              {/* Set */}
              <div style={{ flex: 1, textAlign: 'center' }}>{card.set_name}</div>

              {/* Language */}
              <div style={{ flex: 1, textAlign: 'center' }}>{card.language || 'N/A'}</div>

              {/* Actions */}
              <div style={{ flex: 2, textAlign: 'right' }}>
                <Space>
                  <Button icon={<EyeOutlined />} onClick={() => handleViewCard(card)}>View</Button>
                  <Button
                    icon={<EditOutlined />}
                    onClick={(e) => {
                      e.stopPropagation(); // Prevent the event from propagating to parent handlers
                      handleEditCard(card);
                    }}
                  >
                    Edit
                  </Button>
                  <Popconfirm
                    title="Are you sure you want to delete this card?"
                    onConfirm={() => handleDeleteCard(card.id)}
                    okText="Yes"
                    cancelText="No"
                  >
                    <Button icon={<DeleteOutlined />} danger>Delete</Button>
                  </Popconfirm>
                </Space>
              </div>
            </div>
          </List.Item>
        )}
        className={`ant-table ${theme}`}
      />

      {/* Modal for Viewing Card Details */}
      <Modal
        title={selectedCard ? selectedCard.name : ''}
        open={isModalVisible}
        onCancel={handleModalClose}
        width={800}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Close
          </Button>,
        ]}
      >
        {isLoading ? (
          <Spin size="large" />
        ) : cardData ? (
          console.log('Rendering ScryfallCard, modalMode:', modalMode), // Debug log
          <ScryfallCard 
            data={cardData.scryfall || cardData}
            onPrintingSelect={modalMode === 'edit' ? handleSaveEdit : undefined} // Pass only in "edit" mode
          />
        ) : (
          <div>No card data available</div>
        )}
      </Modal>
    </div>
  );
};

export default CardManagement;