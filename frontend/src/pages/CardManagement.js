import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Table, AutoComplete, Modal, Button, message, Spin, Space, Popconfirm, Form, List, Input, Select } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined, SaveOutlined, FolderOpenOutlined, SearchOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import CardDetail from '../components/CardDetail';
import api from '../utils/api';
import { getStandardTableColumns } from '../utils/tableConfig';
import ScryfallCardView from '../components/Shared/ScryfallCardView';
import debounce from 'lodash/debounce';

const { Option } = Select;

const CardManagement = ({ userId }) => {
  const location = useLocation();
  const initialBuylistName = location?.state?.buylistName || '';
  const initialBuylistId = location?.state?.buylistId;

  console.log('Debug: Location state', location.state);
  console.log('Debug: Initial buylist name and ID', { initialBuylistName, initialBuylistId });

  const [buylistName, setBuylistName] = useState(initialBuylistName);
  
  const [cards, setCards] = useState([]);
  const [filteredCards, setFilteredCards] = useState([]);
  const [searchText, setSearchText] = useState('');
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [modalMode, setModalMode] = useState('view');
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [form] = Form.useForm();
  const { theme } = useTheme();
  const [cardDetailVisible, setCardDetailVisible] = useState(false);
  const [savedBuylists, setSavedBuylists] = useState([]);
  const [currentBuylistId, setCurrentBuylistId] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [cardVersions, setCardVersions] = useState(null);
  const [sets, setSets] = useState([]);
  const [topBuylists, setTopBuylists] = useState([]);

  useEffect(() => {
    console.log('Debug: useEffect for userId', userId);
    if (userId) {
      fetchSavedBuylists();
    }
  }, [userId]);

  useEffect(() => {
    console.log('Debug: useEffect for initialBuylistName and initialBuylistId', { initialBuylistName, initialBuylistId });
    if (initialBuylistName && initialBuylistId) {
      handleLoadBuylist(initialBuylistId);
      message.success('Buylist loaded successfully');
    }
  }, [initialBuylistName, initialBuylistId]);

  const fetchSavedBuylists = async () => {
    try {
      const response = await api.get('/buylists', { params: { user_id: userId } });
      setSavedBuylists(response.data);
    } catch (error) {
      console.error('Debug: Failed to fetch saved buylists', error);
      message.error('Failed to fetch saved buylists');
    }
  };

  const handleSaveBuylist = async () => {
    if (!buylistName && !currentBuylistId) {
      message.error('Please enter a name for the buylist');
      return;
    }

    try {
      const response = await api.post('/buylists', { buylist_id: currentBuylistId, buylist_name: buylistName, user_id: userId, cards });
      message.success('Buylist saved successfully');
      fetchSavedBuylists();
      setCurrentBuylistId(response.data.buylist_id); // Set the current buylist ID
    } catch (error) {
      message.error(`Failed to save buylist: ${error.message}`);
    }
  };

  const handleLoadBuylist = async (buylistId) => {
    try {
      const response = await api.get(`/buylists/${buylistId}`, {
        params: { user_id: userId }
      });
      setCards(response.data);
      setFilteredCards(response.data);
      setCurrentBuylistId(buylistId); 
      setBuylistName(response.data[0]?.buylist_name || ''); 
    } catch (error) {
      console.error('Debug: Failed to load buylist', error);
      message.error(`Failed to load buylist: ${error.message}`);
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
        set: card.set || card.set_code || card.set_name,
        language: card.language || 'en',
        version: card.version || 'Normal',
        user_id: userId // Add user ID
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
          set: card.set,
          language: card.language,
          version: card.version,
          user_id: userId // Add user ID
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
      set: selectedPrinting.set,
      set_name: selectedPrinting.set_name,
      language: selectedPrinting.lang || selectedCard.language,
      quantity: selectedCard.quantity,
      version: selectedPrinting.version || selectedCard.version,
      foil: selectedCard.foil
    };

    console.log('3. Updating card with:', updatedCard);

    try {
      const response = await api.put(`/cards/${selectedCard.id}`, { ...updatedCard, user_id: userId }); // Add user ID
      console.log('4. Update response:', response);

      if (!response.data) {
        throw new Error('No data received from update');
      }

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
      await api.delete(`/cards/${cardId}`, {
        params: { user_id: userId } // Add user ID
      });
      message.success('Card deleted successfully');
      setCards((prev) => prev.filter((card) => card.id !== cardId));
      setFilteredCards((prev) => prev.filter((card) => card.id !== cardId));
    } catch (error) {
      message.error(`Failed to delete card: ${error.message}`);
    }
  };

  const handleSearch = (value) => {
    setSearchText(value);
    debouncedFetchSuggestions(value);
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

  const handleNewBuylist = () => {
    setBuylistName('');
    setCards([]);
    setFilteredCards([]);
    setCurrentBuylistId(null);
    message.success('New buylist created. Please add cards and save.');
  };

  const fetchSuggestions = async (query) => {
    if (query.length > 2) {
      try {
        const response = await api.get(`/card_suggestions?query=${query}`, {
          params: { user_id: userId } 
        });
        console.log('Suggestions received:', response.data);
        setSuggestions(response.data.map(name => ({ value: name })));
      } catch (error) {
        console.error('Error fetching suggestions:', error);
        setSuggestions([]);
      }
    } else {
      setSuggestions([]);
    }
  };

  const fetchCardVersions = async (cardName) => {
    try {
      const response = await api.get(`/card_versions?name=${encodeURIComponent(cardName)}`, {
        params: { user_id: userId } 
      });
      console.log('Card versions received:', response.data);
      setCardVersions(response.data);
      setSets(response.data.sets);
    } catch (error) {
      console.error('Error fetching card versions:', error);
      setCardVersions(null);
      setSets([]);
    }
  };

  const debouncedFetchSuggestions = debounce(fetchSuggestions, 300);

  const handleSelectCard = (value) => {
    const newCard = {
      name: value,
      quantity: 1,
      set_name: '',
      quality: 'NM'
    };
    setCards([...cards, newCard]);
    setFilteredCards([...filteredCards, newCard]);
    setSearchText('');
  };

  const columns = [
    ...getStandardTableColumns(handleViewCard),
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
      <div style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 150px', minWidth: '300px', marginRight: '16px' }}>
          {currentBuylistId && <h3 style={{ fontWeight: 'bold', marginTop: 0 }}>Current buylist: {buylistName}</h3>} {/* Indicate current buylist */}
          <AutoComplete
            value={searchText}
            options={suggestions}
            onSearch={(text) => {
              setSearchText(text);
              handleSearch(text);
            }}
            onSelect={handleSelectCard}
            placeholder="Search cards..."
            style={{ 
              marginBottom: 16,
              width: '100%'
            }}
            prefix={<SearchOutlined />}
          />
          <Input
            placeholder="Buylist name..."
            value={buylistName}
            onChange={(e) => setBuylistName(e.target.value)}
            style={{ 
              marginBottom: 16,
              width: '100%'
            }}
            prefix={<SaveOutlined />}
          />
        </div>
        <div style={{ flex: '1 1 30px', minWidth: '300px', marginRight: '16px' }}>
          
          <h3 style={{ fontWeight: 'bold', marginTop: 0 }}>Actions</h3>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveBuylist}
            style={{ marginBottom: 16, marginRight: 8, width: '100%' }}
          >
            Save Buylist
          </Button>
          <Button
            type="default"
            icon={<FolderOpenOutlined />}
            onClick={handleNewBuylist}
            style={{ marginBottom: 16, width: '100%' }}
          >
            New Buylist
          </Button>
        </div>
        <div style={{ flex: '1 1 300px', minWidth: '300px' }}>
          <h3 style={{ fontWeight: 'bold', marginTop: 0 }}>Saved Buylists</h3>
          <List
            bordered
            dataSource={savedBuylists}
            renderItem={item => (
              <List.Item
                actions={[
                  <Button
                    type="link"
                    icon={<FolderOpenOutlined />}
                    onClick={() => handleLoadBuylist(item.buylist_id)}
                  >
                    Load
                  </Button>
                ]}
                style={item.buylist_id === currentBuylistId ? { fontWeight: 'bold' } : {}}
              >
                {item.buylist_name}
              </List.Item>
            )}
            style={{ marginBottom: 8 }}
          />
        </div>
      </div>
      <h3 style={{ fontWeight: 'bold', marginTop: 24 }}>Buylist Cards</h3>
      <Table
        dataSource={filteredCards}
        columns={columns}
        rowKey="id"
        className={`ant-table ${theme}`}
        onRow={(record) => ({
          onClick: () => handleViewCard(record),
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