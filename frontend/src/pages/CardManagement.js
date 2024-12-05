import React, { useState, useEffect } from 'react';
import { Table, Input, Modal, Button, message, Spin, Space, Popconfirm, Form, List, Tooltip } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined, SearchOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import CardDetail from '../components/CardDetail';
import api from '../utils/api';
import { getStandardTableColumns } from '../utils/tableConfig';
import ScryfallCard from '../components/CardManagement/ScryfallCard'; // Add this import if missing
import ScryfallCardView from '../components/Shared/ScryfallCardView';

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
  const [cardDetailVisible, setCardDetailVisible] = useState(false);

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

  const handleViewCard = async (card) => {
    console.group('View Card Flow');
    console.log('Card record:', {
      name: card.name,
      set: card.set,
      set_name: card.set_name,
      set_code: card.set_code,
      full_record: card
    });
  
    setSelectedCard(card);
    setModalMode('view');
    setIsLoading(true);
    try {
      const params = {
        name: card.name,
        set: card.set || card.set_code || card.set_name, // Try all possible set identifiers
        language: card.language || 'en',
        version: card.version || 'Normal'
      };
      console.log('Request params:', params);
  
      const response = await api.get('/fetch_card', { params });
      console.log('Response:', response.data);
      if (!response.data?.scryfall) {
        throw new Error('Invalid data structure received from backend');
      }
  
      setCardData(response.data.scryfall);
      setIsModalVisible(true);
    } catch (error) {
      console.error('Error fetching card:', error);
      message.error(`Failed to fetch card details: ${error.message}`);
    } finally {
      setIsLoading(false);
      console.groupEnd();
    }
  };

  const handleEditCard = async (card) => {
    setSelectedCard(card);
    setModalMode('edit');
    setIsLoading(true);
    try {
      const response = await api.get('/fetch_card', {
        params: {
          name: card.name,
          set: card.set,  // Use set code instead of set_name
          language: card.language,
          version: card.version
        }
      });

      if (!response.data?.scryfall) {
        throw new Error('Invalid data structure received from backend');
      }

      setCardData(response.data.scryfall);
      setIsModalVisible(true);
    } catch (error) {
      console.error('Error fetching card:', error);
      message.error(`Failed to fetch card details: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCardClick = async (card) => {
    console.group('Card Click Flow');
    console.log('1. Initial card data:', card);
  
    if (!card.name) {
      console.error('Card name missing');
      console.groupEnd();
      message.error('Card name is missing');
      return;
    }
  
    setSelectedCard(card);
    setIsLoading(true);
  
    try {
      console.log('2. Fetching card with params:', {
        name: card.name,
        set: card.set || card.set_code, // Try both set and set_code
        language: card.language,
        version: card.version
      });
  
      const response = await api.get('/fetch_card', {
        params: {
          name: card.name,
          set: card.set || card.set_code, // Try both set and set_code
          language: card.language,
          version: card.version
        }
      });
  
      console.log('3. Raw API response:', response);
      console.log('4. Response data:', response.data);
  
      if (!response.data?.scryfall) {
        throw new Error('Invalid data structure received from backend');
      }
  
      setCardData(response.data.scryfall);
      setIsModalVisible(true);
    } catch (error) {
      console.error('5. Error details:', error);
      message.error(`Failed to fetch card details: ${error.message}`);
    } finally {
      setIsLoading(false);
      console.groupEnd();
    }
  };

  const handleModalClose = () => {
    console.log('Modal closing, clearing states');
    setIsModalVisible(false);
    setSelectedCard(null);
    setCardData(null);
    setModalMode('view');
  };

  const handleSaveEdit = async (selectedPrinting) => {
    console.group('Save Edit Flow');
    console.log('1. Selected printing:', selectedPrinting);
    console.log('2. Selected card:', selectedCard);
  
    if (!selectedCard || !selectedPrinting) {
      console.error('Missing required data');
      console.groupEnd();
      message.error('No card or printing selected');
      return;
    }
  
    const updatedCard = {
      id: selectedCard.id,
      name: selectedPrinting.name,
      set: selectedPrinting.set,        // This will be mapped to set_code in backend
      set_name: selectedPrinting.set_name,
      language: selectedPrinting.lang || selectedCard.language,
      quantity: selectedCard.quantity,
      version: selectedPrinting.version || selectedCard.version,
      foil: selectedCard.foil
    };
  
    console.log('3. Updating card with:', updatedCard);
  
    try {
      const response = await api.put(`/cards/${selectedCard.id}`, updatedCard);
      console.log('4. Update response:', response);
  
      if (!response.data) {
        throw new Error('No data received from update');
      }
  
      // Update local state
      setCards((prevCards) =>
        prevCards.map((card) =>
          card.id === response.data.id ? response.data : card
        )
      );
      setFilteredCards((prevCards) =>
        prevCards.map((card) =>
          card.id === response.data.id ? response.data : card
        )
      );
  
      message.success('Card updated successfully');
      handleModalClose();
    } catch (error) {
      console.error('5. Update error:', error);
      message.error(`Failed to update card: ${error.message}`);
    } finally {
      console.groupEnd();
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

  const handleSearch = (value) => {
    setSearchText(value);
    const filtered = cards.filter((card) =>
      card.name?.toLowerCase().includes(value.toLowerCase())
    );
    setFilteredCards(filtered);
  };

  const handleSetClick = async (setCode) => {
    try {
      console.log('Set clicked:', setCode);
      await api.post('/save_set_selection', { set: setCode });
      message.success('Set selection saved successfully');
    } catch (error) {
      message.error(`Failed to save set: ${error.message}`);
    }
  };

  const columns = [
    ...getStandardTableColumns(handleViewCard), // Use handleViewCard instead of handleCardClick
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button icon={<EyeOutlined />} onClick={(e) => {
            e.stopPropagation();
            handleViewCard(record);
          }}>View</Button>
          <Button icon={<EditOutlined />} onClick={(e) => {
            e.stopPropagation();
            handleEditCard(record);
          }}>Edit</Button>
          <Popconfirm
            title="Are you sure you want to delete this card?"
            onConfirm={(e) => {
              e.stopPropagation();
              handleDeleteCard(record.id);
            }}
            okText="Yes"
            cancelText="No"
          >
            <Button icon={<DeleteOutlined />} danger>Delete</Button>
          </Popconfirm>
        </Space>
      ),
    }
  ];

  return (
    <div className="card-management">
      <h1>Card Management</h1>
      <Input
        placeholder="Search cards..."
        value={searchText}
        onChange={(e) => handleSearch(e.target.value)}
        style={{ 
          marginBottom: 16,
          width: '300px'  // Set a fixed width for the search box
        }}
        prefix={<SearchOutlined />}
      />
      <Table
        dataSource={filteredCards}
        columns={columns}
        rowKey="id"
        className={`ant-table ${theme}`}
        onRow={(record) => ({
          onClick: () => handleViewCard(record), // Use handleViewCard for row clicks
        })}
        pagination={false}
      />
      {selectedCard && (
        <CardDetail
          cardName={selectedCard.name}
          setName={selectedCard.set_name}
          language={selectedCard.language}
          version={selectedCard.version}
          foil={selectedCard.foil}
          isModalVisible={cardDetailVisible}
          onClose={() => setCardDetailVisible(false)}
          onEdit={modalMode === 'edit' ? handleSaveEdit : undefined}
        />
      )}
      <Modal
        title={`${selectedCard ? selectedCard.name : ''} ${modalMode === 'edit' ? '- Edit' : ''}`}
        open={isModalVisible}
        onCancel={handleModalClose}
        width={800}
        destroyOnClose={true}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Close
          </Button>
        ]}
      >
        {console.log('Modal render:', { isLoading, hasCardData: !!cardData, isModalVisible })}
        {isLoading ? (
          <Spin size="large" />
        ) : cardData ? (
          <ScryfallCardView 
            key={`${selectedCard?.id}-${cardData.id}-${modalMode}`}
            cardData={cardData}
            mode={modalMode}
            onPrintingSelect={handleSaveEdit}
            onSetClick={handleSetClick}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin />
            <p>Loading card details...</p>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default CardManagement;