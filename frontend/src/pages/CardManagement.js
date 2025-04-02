import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { Table, AutoComplete, Modal, Button, message, Spin, Space, Popconfirm, Checkbox, List, Input, Select } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined, SaveOutlined, FolderOpenOutlined, SearchOutlined, FilterOutlined, ClearOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import CardDetail from '../components/CardDetail';
import api from '../utils/api';
import { getStandardTableColumns, getColumnSearchProps } from '../utils/tableConfig';
import ScryfallCardView from '../components/Shared/ScryfallCardView';
import ImportCardsToBuylist from '../components/CardManagement/ImportCardsToBuylist';
import debounce from 'lodash/debounce';

const { Option } = Select;
const { TextArea } = Input;

const BuylistManagement = ({ userId }) => {
  const location = useLocation();
  const initialBuylistName = location?.state?.buylistName || '';
  const initialBuylistId = location?.state?.buylistId;
  
  const [cards, setCards] = useState([]);
  const [filteredCards, setFilteredCards] = useState([]);
  const [searchText, setSearchText] = useState({});
  const [filteredInfo, setFilteredInfo] = useState({});
  const [searchedColumn, setSearchedColumn] = useState('');
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [modalMode, setModalMode] = useState('view');
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const { theme } = useTheme();
  const [cardDetailVisible, setCardDetailVisible] = useState(false);
  const [savedBuylists, setSavedBuylists] = useState([]);
  const [currentBuylistId, setCurrentBuylistId] = useState(initialBuylistId || null); 
  const [currentBuylistName, setCurrentBuylistName] = useState(initialBuylistName);
  const [loadedBuylistName, setLoadedBuylistName] = useState("");
  
  const [suggestions, setSuggestions] = useState([]);
  const [cardVersions, setCardVersions] = useState(null);
  const [sets, setSets] = useState([]);
  const [cardText, setCardText] = useState('');
  const [errorCards, setErrorCards] = useState([]);

  const [selectedCardIds, setSelectedCardIds] = useState(new Set());
  const [selectAllChecked, setSelectAllChecked] = useState(false);
  const searchInput = useRef(null);

  // Fetch saved buylists and set the initial buylist
  useEffect(() => {
    const initializeBuylists = async () => {
      setErrorCards([]);
      try {
        const response = await api.get('/buylists', { params: { user_id: userId } });

        if (response.data.length > 0) {
          setSavedBuylists(response.data);

          // Determine the buylist to load
          if (initialBuylistId) {
            setCurrentBuylistId(initialBuylistId);
            setCurrentBuylistName(initialBuylistName);
            setLoadedBuylistName(initialBuylistName);
          } else {
            const firstBuylist = response.data[0];
            setCurrentBuylistId(firstBuylist.id);
            setCurrentBuylistName(firstBuylist.name);
            setLoadedBuylistName(firstBuylist.name);
          }
        }
      } catch (error) {
        console.error('Failed to fetch saved buylists:', error);
        message.error('Failed to fetch saved buylists.');
      }
    };

    initializeBuylists();
  }, [userId, initialBuylistId, initialBuylistName]);

  // Load cards for the current buylist
  useEffect(() => {
    setErrorCards([]);
    const loadBuylist = async (buylistId) => {
      if (!buylistId) return;

      try {
        const response = await api.get(`/buylists/${buylistId}`, { params: { user_id: userId } });

        // Ensure response.data is always an array
        const cards = Array.isArray(response.data) ? response.data : [];

        setCards(cards);
        setFilteredCards(cards);

        if (cards.length > 0) {
          message.success(`Buylist "${currentBuylistName}" loaded successfully.`);
        } else {
          message.info(`Buylist "${currentBuylistName}" is empty.`);
        }
      } catch (error) {
        console.error('Failed to load buylist:', error);
        message.error('Failed to load buylist.');
      }
    };

    loadBuylist(currentBuylistId);
  }, [currentBuylistId]);

  // Handle search text changes and filter cards
  useEffect(() => {
    const applyFilters = () => {
      let filtered = [...cards];
      
      // Apply search text filtering
      if (searchText.name) {
        filtered = filtered.filter(card => 
          card.name.toLowerCase().includes(searchText.name.toLowerCase())
        );
      }
      
      if (searchText.set_name) {
        filtered = filtered.filter(card => 
          card.set_name?.toLowerCase().includes(searchText.set_name.toLowerCase())
        );
      }
      
      // Apply other filters from filteredInfo
      if (filteredInfo.quality?.length) {
        filtered = filtered.filter(card => 
          filteredInfo.quality.includes(card.quality)
        );
      }
      
      if (filteredInfo.language?.length) {
        filtered = filtered.filter(card => 
          filteredInfo.language.includes(card.language)
        );
      }
      
      setFilteredCards(filtered);
    };
    
    applyFilters();
  }, [cards, searchText, filteredInfo]);

  // Console logs for debugging
  useEffect(() => {
    setErrorCards([]);
    console.log("Updated buylistId:", currentBuylistId);
    console.log("Updated buylistName:", currentBuylistName);
  }, [currentBuylistId, currentBuylistName]);

  // Search handlers
  const handleSearch = (selectedKeys, confirm, dataIndex) => {
    confirm();
    setSearchText({ ...searchText, [dataIndex]: selectedKeys[0] });
    setSearchedColumn(dataIndex);
  };

  const handleReset = (clearFilters, dataIndex) => {
    clearFilters();
    setSearchText(prev => ({ ...prev, [dataIndex]: '' }));
    setFilteredInfo(prev => ({ ...prev, [dataIndex]: null }));
  };

  const handleResetAllFilters = () => {
    setFilteredInfo({});
    setSearchText({});
    setSearchedColumn('');
    if (searchInput.current) {
      Object.values(searchInput.current).forEach(input => {
        if (input) {
          input.value = '';
        }
      });
    }
    setFilteredCards(cards);
  };

  const fetchSavedBuylists = async () => {
    try {
      const response = await api.get('/buylists', { params: { user_id: userId } });
      if (response.data) {
        setSavedBuylists(response.data);
        setCurrentBuylistId(response.data[0]?.id);
        console.log('currentBuylistId in fetchSavedBuylists:', currentBuylistId);
        setCurrentBuylistName(response.data[0]?.name);
        setLoadedBuylistName(response.data[0]?.name);
      }
    } catch (error) {
      console.error('Debug: Failed to fetch saved buylists', error);
      message.error('Failed to fetch saved buylists');
    }
  };

  const handleSaveBuylist = async () => {
    setErrorCards([]);
    if (!currentBuylistId || !currentBuylistName) {
      message.error('Buylist ID and name are required.');
      return;
    }
  
    try {
      const response = await api.put(`/buylists/${currentBuylistId}/rename`, {
        name: currentBuylistName,
        user_id: userId
      });
  
      const updatedBuylist = response.data;
  
      // Update saved buylists in state:
      setSavedBuylists(prev =>
        prev.map(buylist =>
          buylist.id === currentBuylistId ? { ...buylist, name: updatedBuylist.name } : buylist
        )
      );
  
      message.success('Buylist name updated successfully.');
    } catch (error) {
      message.error('Failed to rename buylist.');
      console.error('Error renaming buylist:', error);
    }
  };
  
  const handleCardImport = (addedCards) => {
    setErrorCards([]);
    setCards((prevCards) => {
      const existingNames = new Set(prevCards.map(card => card.name.toLowerCase()));
      const uniqueCards = addedCards.filter(card => !existingNames.has(card.name.toLowerCase()));

      return [...prevCards, ...uniqueCards];
    });

    message.success('Cards imported successfully.');
  };

  const handleViewCard = async (card) => {
    setErrorCards([]);
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
        user_id: userId
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
    setErrorCards([]);
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
          user_id: userId
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
    setErrorCards([]);
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
      set_code: selectedPrinting.set_code,
      set_name: selectedPrinting.set_name,
      language: selectedPrinting.language || selectedCard.language,
      quantity: selectedCard.quantity,
      version: selectedPrinting.version || selectedCard.version,
      foil: selectedCard.foil,
      buylist_id: selectedCard.buylist_id,
      user_id: userId
    };
    console.log('3. Updating card with:', updatedCard);

    try {
      const response = await api.put(`/buylist/cards/${selectedCard.id}`, updatedCard);
      console.log('4. Update response:', response);

      if (!response.data) {
        throw new Error('No data received from update');
      }

      setCards((prevCards) =>
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

  const handleDeleteCards = async (selectedCards) => {
    setErrorCards([]);
    if (!selectedCards.length) {
        message.warning("No cards selected for deletion.");
        return;
    }

    try {
        await api.delete("/buylist/cards", {
            data: {
                id: currentBuylistId,
                user_id: userId,
                cards: selectedCards,
            }
        });

        message.success(`${selectedCards.length} card(s) deleted successfully.`);

        // Update state: Remove deleted cards from the UI
        setCards((prev) => prev.filter((card) => !selectedCards.some((c) => c.id === card.id)));

        // Clear selection after deletion
        setSelectedCardIds(new Set());
        setSelectAllChecked(false);
    } catch (error) {
        message.error("Failed to delete cards.");
        console.error("Error deleting cards:", error);
    }
  };

  // Handle individual checkbox selection
  const handleCheckboxChange = (cardId) => {
    setErrorCards([]);
    setSelectedCardIds((prev) => {
      const newSelection = new Set(prev);
      if (newSelection.has(cardId)) {
          newSelection.delete(cardId);
      } else {
          newSelection.add(cardId);
      }
      setSelectAllChecked(newSelection.size === filteredCards.length);
      return newSelection;
    });
  };

  // Handle "Select All" checkbox
  const handleSelectAll = () => {
    setErrorCards([]);
    if (selectAllChecked) {
      setSelectedCardIds(new Set());
    } else {
      setSelectedCardIds(new Set(filteredCards.map((card) => card.id)));
    }
    setSelectAllChecked(!selectAllChecked);
  };

  const handleSuggestionSearch = (value) => {
    setErrorCards([]);
    debouncedFetchSuggestions(value);
  };

  const handleSetClick = async (setCode) => {
    setErrorCards([]);
    try {
      console.log('Set clicked:', setCode);
      await api.post('/save_set_selection', { set: setCode });
      message.success('Set selection saved successfully');
    } catch (error) {
      message.error(`Failed to save set: ${error.message}`);
    }
  };

  const handleNewBuylist = async () => {
    setErrorCards([]);

    const trimmedBuylistName = 
      currentBuylistName.trim() !== loadedBuylistName.trim()
          ? currentBuylistName.trim() || "Untitled Buylist"
          : "Untitled Buylist";

    try {
      const response = await api.post("/buylists", {
          name: trimmedBuylistName,
          user_id: userId,
          cards: []
      });

      const newBuylist = response.data;

      setCurrentBuylistId(newBuylist.id);
      setCurrentBuylistName(newBuylist.name);
      setLoadedBuylistName(newBuylist.name);
      setCards([]);
      setFilteredCards([]);
      setSearchText({});
      setErrorCards([]);
      setCardText("");

      // Update Saved Buylists list immediately
      setSavedBuylists((prevBuylists) => [
          ...prevBuylists,
          { id: newBuylist.id, name: newBuylist.name }
      ]);

      message.success(`New buylist "${newBuylist.name}" created.`);
    } catch (error) {
      message.error("Failed to create a new buylist.");
      console.error("Error creating new buylist:", error);
    }
  };

  const handleDeleteBuylist = async (buylistId) => {
    setErrorCards([]);
    Modal.confirm({
      title: "Are you sure you want to delete this buylist?",
      content: "This action cannot be undone.",
      okText: "Yes, delete",
      okType: "danger",
      cancelText: "Cancel",
      onOk: async () => {
          try {
              await api.delete(`/buylists/${buylistId}`, { params: { user_id: userId } });
              message.success("Buylist deleted successfully.");
              fetchSavedBuylists();
              
              if (currentBuylistId === buylistId) {
                  setCurrentBuylistId(null);
                  setCurrentBuylistName("");                  
                  setLoadedBuylistName("");
                  setCards([]);
              }
          } catch (error) {
              message.error("Failed to delete buylist.");
              console.error("Error deleting buylist:", error);
          }
      }
    });
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
    setSuggestions([]);
  };

  // Create columns with the shared utility
  const tableColumns = [
    ...getStandardTableColumns(
      handleViewCard, 
      searchInput, 
      filteredInfo, 
      handleSearch, 
      handleReset
    ),
    {
      title: "Actions",
      key: "actions",
      className: "actions-column",
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
                  handleDeleteCards([record]);
              }}
              okText="Yes"
              cancelText="No"
          >
              <Button icon={<DeleteOutlined />} danger>Delete</Button>
          </Popconfirm>
        </Space>
      ),
    },
    {
      title: (
        <Checkbox
          checked={selectAllChecked}
          onChange={(e) => {
              e.stopPropagation();
              handleSelectAll();
          }}
        />
      ),
      dataIndex: "checkbox",
      key: "checkbox",
      align: "center",
      render: (_, record) => (
        <Checkbox
            checked={selectedCardIds.has(record.id)}
            onChange={(e) => {
                e.stopPropagation();
                handleCheckboxChange(record.id);
            }}
        />
      ),
    },
  ];

  return (
    <div className="buylist-management">
      <h1>Buylist Management</h1>
      <div style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 150px', minWidth: '150px', marginLeft: '16px' , marginRight: '16px' }}>
          {currentBuylistId && <h3 style={{ fontWeight: 'bold', marginTop: 0 }}>Current buylist: {currentBuylistName}</h3>}
          <AutoComplete
            options={suggestions}
            onSearch={handleSuggestionSearch}
            onSelect={handleSelectCard}
            placeholder="Add card..."
            style={{ 
              marginBottom: 16,
              width: '100%'
            }}
            prefix={<SearchOutlined />}
          />
          <div style={{ flex: 2 }}>
            <ImportCardsToBuylist 
              buylistId={currentBuylistId}
              onCardsAdded={handleCardImport}
              userId={userId}
              cardText={cardText}
              setCardText={setCardText}
              errorCards={errorCards}
              setErrorCards={setErrorCards}
            />
          </div>
        </div>
        <div style={{ flex: '1 1 30px', minWidth: '300px', marginRight: '16px' }}>
          
          <h3 style={{ fontWeight: 'bold', marginTop: 0 }}>Actions</h3>
          <Input
            placeholder="Buylist name..."
            value={currentBuylistName}
            onChange={(e) => setCurrentBuylistName(e.target.value)}
            style={{ 
              marginBottom: 16,
              width: '100%'
            }}
            prefix={<SaveOutlined />}
          />
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
            style={{ marginBottom: 8 }}
            renderItem={(item) => (
              <List.Item
                style={item.id === currentBuylistId ? { fontWeight: 'bold' } : {}}
              >
                <Button
                  type="link"
                  icon={<FolderOpenOutlined />}
                  onClick={() => {
                    setCurrentBuylistId(item.id);
                    setCurrentBuylistName(item.name);
                    setLoadedBuylistName(item.name);
                  }}
                  style={{ marginRight: 8 }}
                >
                  Load
                </Button>
                <Button
                  type="link"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeleteBuylist(item.id)}
                >
                  Delete
                </Button>
                {item.name} {item.cards_count !== undefined ? `(${item.cards_count})` : ''}
              </List.Item>
            )}
          />
        </div>
      </div>
      <h3 style={{ fontWeight: 'bold', marginTop: 24 , marginLeft: '16px'}}>Buylist Cards</h3>
      <div style={{ marginBottom: 16, marginLeft: '16px' }}>
        {selectedCardIds.size > 0 && (
          <Button
            type="primary"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteCards(filteredCards.filter((card) => selectedCardIds.has(card.id)))}
            style={{ marginRight: 8 }}
          >
            Delete Selected ({selectedCardIds.size})
          </Button>
        )}
        <Button
          onClick={handleResetAllFilters}
          icon={<ClearOutlined />}
        >
          Reset All Filters
        </Button>
      </div>
      <Table
        dataSource={filteredCards}
        columns={tableColumns}
        rowKey="id"
        className={`ant-table ${theme}`}
        onRow={(record) => ({
          onClick: (e) => {
            if ((!e.target.closest(".actions-column")) && 
                 !e.target.closest(".ant-checkbox-wrapper")) 
            {  // Ignore clicks inside buttons
              handleViewCard(record);
            }
          },
        })}
        onChange={(pagination, filters) => {
          setFilteredInfo(filters);
        }}
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '50', '100'],
          showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} items`
        }}
        style={{ marginLeft: '16px', marginRight: '16px' }}
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

export default BuylistManagement;