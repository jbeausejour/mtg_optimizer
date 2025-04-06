import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { useLocation } from 'react-router-dom';
import { Modal, Button, message, Spin, Space, Input, Select, Typography, Form, Switch, List, AutoComplete } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined, SearchOutlined, ClearOutlined, SaveOutlined, FolderOpenOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import api from '../utils/api';
import { getStandardTableColumns } from '../utils/tableConfig';
import ScryfallCardView from '../components/Shared/ScryfallCardView';
import ImportCardsToBuylist from '../components/CardManagement/ImportCardsToBuylist';
import ColumnSelector from '../components/ColumnSelector';
import { ExportOptions } from '../utils/exportUtils';
import EnhancedTable from '../components/EnhancedTable';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';
import debounce from 'lodash/debounce';

const { Title, Text } = Typography;
const { Option } = Select;
const { TextArea } = Input;

const BuylistManagement = ({ userId }) => {
  const location = useLocation();
  const initialBuylistName = location?.state?.buylistName || '';
  const initialBuylistId = location?.state?.buylistId;
  const queryClient = useQueryClient();
  
  const { theme } = useTheme();
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Modal state for card detail view/edit
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [modalMode, setModalMode] = useState('view');
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isCardLoading, setIsCardLoading] = useState(false);
  
  // Buylist management state
  const [savedBuylists, setSavedBuylists] = useState([]);
  const [currentBuylistId, setCurrentBuylistId] = useState(initialBuylistId || null); 
  const [currentBuylistName, setCurrentBuylistName] = useState(initialBuylistName);
  const [loadedBuylistName, setLoadedBuylistName] = useState("");
  
  // Card search and import state - Restored from old version
  const [suggestions, setSuggestions] = useState([]);
  const [cardText, setCardText] = useState('');
  const [errorCards, setErrorCards] = useState([]);
  
  // Use our enhanced table handler for consistent behavior
  const {
    filteredInfo,
    sortedInfo,
    pagination,
    selectedIds: selectedCardIds,
    setSelectedIds: setSelectedCardIds,
    searchInput,
    visibleColumns,
    handleTableChange,
    handleSearch,
    handleReset,
    handleResetAllFilters,
    handleColumnVisibilityChange
  } = useEnhancedTableHandler(
    {
      visibleColumns: [
        'name', 'set_name', 'price', 'quality', 'quantity', 'language', 'actions'
      ]
    }, 
    'card_management_table'
  );
  
  // Delete mutation for single card
  const deleteCardMutation = useMutation(
    ({ id, cardData }) => api.delete('/buylist/cards', {
      data: { 
        id: currentBuylistId, 
        user_id: userId, 
        cards: [cardData]
      }
    }),
    {
      // Optimistic update - remove the item immediately from UI
      onMutate: async (cardId) => {
        // Cancel any outgoing refetches
        await queryClient.cancelQueries(['buylist', currentBuylistId, userId]);
        
        // Save the previous cards
        const previousCards = queryClient.getQueryData(['buylist', currentBuylistId, userId]) || [...cards];
        
        // Optimistically update the UI
        setCards(prev => prev.filter(card => card.id !== cardId));
        
        // Update selection state if necessary
        setSelectedCardIds(prev => {
          const newSet = new Set(prev);
          newSet.delete(cardId);
          return newSet;
        });
        
        // Return the previous value in case of rollback
        return { previousCards };
      },
      onError: (err, cardId, context) => {
        // Roll back to the previous value if there's an error
        setCards(context.previousCards);
        message.error('Failed to delete card.');
      },
      onSuccess: () => {
        message.success('Card deleted successfully.');
      },
      onSettled: () => {
        // Always refetch after error or success
        queryClient.invalidateQueries(['buylist', currentBuylistId, userId]);
      }
    }
  );
  
  // Fetch saved buylists
  useEffect(() => {
    const initializeBuylists = async () => {
      setErrorCards([]);
      try {
        const response = await api.get('/buylists', { params: { user_id: userId } });
        if (response.data.length > 0) {
          setSavedBuylists(response.data);
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
  
  // Load cards for current buylist
  useEffect(() => {
    const loadBuylist = async (buylistId) => {
      if (!buylistId) return;
      setLoading(true);
      try {
        const response = await api.get(`/buylists/${buylistId}`, { params: { user_id: userId } });
        const cardsData = Array.isArray(response.data) ? response.data : [];
        setCards(cardsData);
        if (cardsData.length > 0) {
          message.success(`Buylist "${currentBuylistName}" loaded successfully.`);
        } else {
          message.info(`Buylist "${currentBuylistName}" is empty.`);
        }
      } catch (error) {
        console.error('Failed to load buylist:', error);
        message.error('Failed to load buylist.');
      } finally {
        setLoading(false);
      }
    };
    loadBuylist(currentBuylistId);
  }, [currentBuylistId, currentBuylistName, userId]);
  
  // Update effects when cards change - Restored from old version
  useEffect(() => {
    // This effect runs every time the `cards` array changes.
    setSavedBuylists(current =>
      current.map(buylist =>
        buylist.id === currentBuylistId
          ? { ...buylist, cards_count: cards.length }
          : buylist
      )
    );
    
    // console.log('Table items have changed. New cards:', cards);
  }, [cards, currentBuylistId]);
  
  // Column definitions for cards table
  const cardColumns = useMemo(() => {
    // Use standard table columns for cards with search props and click handler for card details
    const baseColumns = getStandardTableColumns(
      (record) => handleViewCard(record),
      searchInput,
      filteredInfo,
      handleSearch,
      handleReset
    );
    
    // Add an "Actions" column for edit and delete buttons
    return [
      ...baseColumns,
      {
        title: 'Actions',
        key: 'actions',
        render: (_, record) => (
          <Space>
            <Button type="link" icon={<EyeOutlined />} onClick={(e) => { e.stopPropagation(); handleViewCard(record); }}>
              View
            </Button>
            <Button type="link" icon={<EditOutlined />} onClick={(e) => { e.stopPropagation(); handleEditCard(record); }}>
              Edit
            </Button>
            <Button type="link" danger icon={<DeleteOutlined />} onClick={(e) => { e.stopPropagation(); handleDeleteCard(record.id); }}>
              Delete
            </Button>
          </Space>
        )
      }
    ];
  }, [filteredInfo, handleSearch, handleReset]);
  
  ////////////////////////////////////////
  // Buylist Management Handlers - Restored from old version
  ////////////////////////////////////////
  const fetchSavedBuylists = async () => {
    try {
      const response = await api.get('/buylists', { params: { user_id: userId } });
      if (response.data) {
        setSavedBuylists(response.data);
        setCurrentBuylistId(response.data[0]?.id);
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
  
  ////////////////////////////////////////
  // Card Import and Edit Handlers - Restored from old version
  ////////////////////////////////////////
  const handleCardImport = (addedCards) => {
    setErrorCards([]);
    
    // Process cards to ensure they have unique IDs
    const processedCards = addedCards.map(card => {
      if (!card.id) {
        // Generate a temporary client-side ID if server doesn't provide one
        const clientSideId = `temp-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
        return { ...card, id: clientSideId };
      }
      return card;
    });
    
    setCards((prevCards) => {
      const existingNames = new Set(prevCards.map(card => card.name.toLowerCase()));
      const uniqueCards = processedCards.filter(card => !existingNames.has(card.name.toLowerCase()));
      return [...prevCards, ...uniqueCards];
    });
    
    // Reset selection state after import
    setSelectedCardIds(new Set());
    
    message.success('Cards imported successfully.');
  };

  const handleSuggestionSearch = (value) => {
    setErrorCards([]);
    debouncedFetchSuggestions(value);
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

  const debouncedFetchSuggestions = debounce(fetchSuggestions, 300);
  
  const handleSelectCard = useCallback(async (value) => {
    // Generate a temporary client-side ID
    const clientSideId = `temp-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    
    // Create the new card object
    const newCard = {
      id: clientSideId,
      name: value,
      quantity: 1,
      set_name: '',
      quality: 'NM'
    };
    
    // Optimistically update UI first
    setCards(prevCards => [...prevCards, newCard]);
    setSuggestions([]);
    
    try {
      // Save the card to the server
      const response = await api.post(`/buylists/${currentBuylistId}/cards`,  {
        user_id: userId,
        cards: [{
          name: value,
          quantity: 1,
          quality: 'NM',
          language: 'English',       // default value
          set_name: '',              // default value
          set_code: '',              // default value
          version: 'Standard',       // default value
          foil: false                // default value
        }]
      });
      
      // If successful, update the card with the server-provided ID
      if (response.data && response.data.addedCards && response.data.addedCards.length > 0) {
        const serverCard = response.data.addedCards[0];
        
        // Replace the temporary card with the server version
        setCards(prevCards => prevCards.map(card => 
          card.id === clientSideId ? { ...serverCard, id: serverCard.id } : card
        ));
        
        console.log('Card added successfully:', serverCard);
        message.success('Card(s) added successfully.');
      }
    } catch (error) {
      console.error('Error adding card:', error);
      message.error(`Failed to add card: ${error.message}`);
      
      // Remove the card from UI if the API call fails
      setCards(prevCards => prevCards.filter(card => card.id !== clientSideId));
    }
  }, [currentBuylistId, userId, setCards]);

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
  
  // Handlers for card view/edit
  const handleViewCard = useCallback(async (card) => {
    setSelectedCard(card);
    setModalMode('view');
    setIsCardLoading(true);
    try {
      const params = {
        name: card.name,
        set: card.set || card.set_code || card.set_name,
        language: card.language || 'en',
        version: card.version || 'Normal',
        user_id: userId
      };
      const response = await api.get('/fetch_card', { params });
      if (!response.data?.scryfall) throw new Error('Invalid card data');
      setCardData(response.data.scryfall);
      setIsModalVisible(true);
    } catch (error) {
      console.error('Error fetching card:', error);
      message.error(`Failed to fetch card details: ${error.message}`);
    } finally {
      setIsCardLoading(false);
    }
  }, [userId]);
  
  const handleEditCard = useCallback(async (card) => {
    setSelectedCard(card);
    setModalMode('edit');
    setIsCardLoading(true);
    try {
      const params = {
        name: card.name,
        set: card.set || card.set_code || card.set_name,
        language: card.language || 'en',
        version: card.version || 'Normal',
        user_id: userId
      };
      const response = await api.get('/fetch_card', { params });
      if (!response.data?.scryfall) throw new Error('Invalid card data');
      setCardData(response.data.scryfall);
      setIsModalVisible(true);
    } catch (error) {
      console.error('Error fetching card:', error);
      message.error(`Failed to fetch card details: ${error.message}`);
    } finally {
      setIsCardLoading(false);
    }
  }, [userId]);
  
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
  
  const handleDeleteCard = useCallback((cardId) => {
    // Find the card object
    const cardToDelete = cards.find(card => card.id === cardId);
    if (!cardToDelete) {
      message.error('Card not found');
      return;
    }
    
    // Call the mutation with the proper card object format
    deleteCardMutation.mutate({
      id: cardId,
      cardData: {
        name: cardToDelete.name,
        quantity: cardToDelete.quantity || 1
      }
    });
  }, [deleteCardMutation, cards]);
  
  const handleModalClose = () => {
    console.log('Modal closing, clearing states');
    setIsModalVisible(false);
    setSelectedCard(null);
    setCardData(null);
    setModalMode('view');
  };
  
  // Handler for bulk deletion 
// Handler for bulk deletion 
const handleBulkDelete = useCallback(() => {
  if (selectedCardIds.size === 0) {
    message.warning('No cards selected for deletion.');
    return;
  }
  
  Modal.confirm({
    title: `Are you sure you want to delete ${selectedCardIds.size} card(s)?`,
    content: 'This action cannot be undone.',
    okText: 'Yes, delete',
    okType: 'danger',
    cancelText: 'Cancel',
    onOk: async () => {
      try {
        // Store the count before clearing for the success message
        const count = selectedCardIds.size;
        
        // Get the full card objects instead of just IDs
        const cardsToDelete = cards.filter(card => selectedCardIds.has(card.id))
          .map(card => ({
            name: card.name,
            quantity: card.quantity || 1
          }));
        
        // Optimistically update the UI
        setCards(prev => prev.filter(card => !selectedCardIds.has(card.id)));
        
        // Send card objects to the API
        await api.delete('/buylist/cards', {
          data: {
            id: currentBuylistId,
            user_id: userId,
            cards: cardsToDelete
          }
        });
        
        // Clear selection and show success
        setSelectedCardIds(new Set());
        message.success(`${count} card(s) deleted successfully.`);
      } catch (error) {
        console.error('Bulk deletion error:', error);
        message.error('Failed to delete selected cards.');
        
        // Refresh data from the server to ensure consistency
        queryClient.invalidateQueries(['buylist', currentBuylistId, userId]);
      }
    }
  });
}, [selectedCardIds, currentBuylistId, userId, setSelectedCardIds, cards, queryClient]);
  
  return (
    <div className={`card-management ${theme}`}>
      <Title level={2}>Buylist Management</Title>
      
      {/* Restored UI Layout from old version - Three column layout */}
      <div style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 24 }}>
        {/* Column 1: Card search and import */}
        <div style={{ flex: '1 1 150px', minWidth: '150px', marginRight: '16px' }}>
          {currentBuylistId && <Title level={4} style={{ marginTop: 0 }}>Current buylist: {currentBuylistName}</Title>}
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
        
        {/* Column 2: Buylist actions */}
        <div style={{ flex: '1 1 150px', minWidth: '150px', marginRight: '16px' }}>
          <Title level={4} style={{ marginTop: 0 }}>Actions</Title>
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
            style={{ marginBottom: 16, width: '100%' }}
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
        
        {/* Column 3: Saved buylists */}
        <div style={{ flex: '1 1 150px', minWidth: '150px' }}>
          <Title level={4} style={{ marginTop: 0 }}>Saved Buylists</Title>
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
      
      {/* Refactored Table Controls */}
      <Title level={4}>Buylist Cards</Title>
      <Space style={{ marginBottom: 16 }}>
        <ColumnSelector 
          columns={cardColumns}
          visibleColumns={visibleColumns}
          onColumnToggle={handleColumnVisibilityChange}
          persistKey="card_management_columns"
        />
        <ExportOptions 
          dataSource={cards} 
          columns={cardColumns}
          filename="cards_export"
        />
        <Button icon={<ClearOutlined />} onClick={handleResetAllFilters}>
          Reset All Filters
        </Button>
        {selectedCardIds.size > 0 && (
          <Button danger onClick={handleBulkDelete} icon={<DeleteOutlined />}>
            Delete Selected ({selectedCardIds.size})
          </Button>
        )}
      </Space>
      
      {/* Refactored Table Component */}
      <EnhancedTable
        dataSource={cards}
        columns={cardColumns.filter(col => visibleColumns.includes(col.key) || col.key === 'actions')}
        rowKey="id"
        loading={loading}
        persistStateKey="card_management_table"
        rowSelectionEnabled={true}
        selectedIds={selectedCardIds}
        onSelectionChange={setSelectedCardIds}
        onRowClick={handleViewCard}
        onChange={handleTableChange}
      />
      
      {/* Card Detail Modal */}
      <Modal
        title={selectedCard?.name}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setIsModalVisible(false)}>
            Close
          </Button>
        ]}
        width={800}
        destroyOnClose
      >
        {isCardLoading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin size="large" />
            <p>Loading card details...</p>
          </div>
        ) : cardData ? (
          <ScryfallCardView 
            key={`${selectedCard?.id}-${cardData.id}`}
            cardData={cardData}
            mode={modalMode}
            onPrintingSelect={handleSaveEdit}
            onSetClick={handleSetClick}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <p>No card data available</p>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default BuylistManagement;