import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useMutation, useQueryClient} from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { Modal, Button, message, Spin, Space, Input, Typography, Popconfirm , List, AutoComplete } from 'antd';
import { EditOutlined, DeleteOutlined, SearchOutlined, ClearOutlined, SaveOutlined, FolderOpenOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import api from '../utils/api';
import { useBuylistState } from '../hooks/useBuylistState';
import { getStandardTableColumns } from '../utils/tableConfig';
import ScryfallCardView from '../components/Shared/ScryfallCardView';
import ImportCardsToBuylist from '../components/CardManagement/ImportCardsToBuylist';
import ColumnSelector from '../components/ColumnSelector';
import { ExportOptions } from '../utils/exportUtils';
import EnhancedTable from '../components/EnhancedTable';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';
import { useFetchScryfallCard } from '../hooks/useFetchScryfallCard';
import debounce from 'lodash/debounce';

const { Title} = Typography;


const BuylistManagement = () => {
  const location = useLocation();
  const { theme } = useTheme();
  const { selectedBuylist, setSelectedBuylist } = useBuylistState();

  const initialBuylistId = location?.state?.buylistId || null;
  const initialBuylistName = location?.state?.buylistName || "";
  const queryClient = useQueryClient();
  
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Modal state for card detail view/edit
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [modalMode, setModalMode] = useState('view');
  const [selectedCard, setSelectedCard] = useState(null);
  
  // Buylist management state
  const [savedBuylists, setSavedBuylists] = useState([]);
  const [loadedBuylistName, setLoadedBuylistName] = useState("");
  const [pendingSelection, setPendingSelection] = useState(null);
  
  // Card search and import state - Restored from old version
  const [suggestions, setSuggestions] = useState([]);
  const [cardText, setCardText] = useState('');
  const [errorCards, setErrorCards] = useState([]);

  const [cardData, setFetchedCard] = useState(null);
  const {
    mutateAsync: fetchCard,
  } = useFetchScryfallCard();
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
  const deleteCardMutation = useMutation({
    mutationFn: ({ card_id, cardData }) => api.delete('/buylist/cards', {
      data: { 
        buylistid: selectedBuylist?.buylistId, 
        cards: [cardData]
      }
    }),
      // Optimistic update - remove the item immediately from UI
      onMutate: async (cardId) => {
        // Cancel any outgoing refetches
        await queryClient.cancelQueries(['buylist', selectedBuylist?.buylistId]);
        
        // Save the previous cards
        const previousCards = queryClient.getQueryData(['buylist', selectedBuylist?.buylistId]) || [...cards];
        
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
        queryClient.invalidateQueries(['buylist', selectedBuylist?.buylistId]);
      }
    }
  );

  const bulkDeleteCardsMutation = useMutation({
    mutationFn: async ({ cardsToDelete }) => {
      return await api.delete('/buylist/cards', {
        data: {
          buylistid: selectedBuylist?.buylistId,

          cards: cardsToDelete
        }
      });
    },
    onSuccess: (data, variables) => {
      message.success(`${variables.cardsToDelete.length} card(s) deleted successfully.`);
      queryClient.invalidateQueries(['buylist', selectedBuylist?.buylistId]);
    },
    onError: (error) => {
      console.error('Bulk deletion error:', error);
      message.error('Failed to delete selected cards.');
      queryClient.invalidateQueries(['buylist', selectedBuylist?.buylistId]);
    }
  });

  const deleteBuylistMutation = useMutation({
    mutationFn: async ({ buylistId }) => {
      return await api.delete(`/buylists/${buylistId}`);
    },
    onSuccess: (_, { buylistId }) => {
      message.success("Buylist deleted successfully.");
      fetchSavedBuylists();
  
      if (selectedBuylist?.buylistId === buylistId) {
        setSelectedBuylist({ buylistId: null, name: "" });
        setLoadedBuylistName("");
        setCards([]);
      }
    },
    onError: (error) => {
      console.error("Error deleting buylist:", error);
      message.error("Failed to delete buylist.");
    }
  });
  
  useEffect(() => {
    const initializeBuylists = async () => {
      setErrorCards([]);
      setLoading(true);
      try {
        const response = await api.get('/buylists');
  
        if (response.data.length === 0) return;
  
        setSavedBuylists(response.data);
  
        const selected = initialBuylistId
          ? { buylistId: initialBuylistId, name: initialBuylistName }
          : { buylistId: response.data[0].id, name: response.data[0].name };
  
        const cardsRes = await api.get(`/buylists/${selected.buylistId}`);
  
        const cardsData = Array.isArray(cardsRes.data) ? cardsRes.data : [];
  
        setCards(cardsData);
        setSelectedBuylist(selected);
        setLoadedBuylistName(selected.name);
  
        // Sync cards_count immediately to prevent flicker
        setSavedBuylists(prev =>
          prev.map(b =>
            b.buylistId === selected.buylistId ? { ...b, cards_count: cardsData.length } : b
          )
        );
  
        if (cardsData.length > 0) {
          message.success(`Buylist "${selected.name}" loaded successfully.`);
        } else {
          message.info(`Buylist "${selected.name}" is empty.`);
        }
  
      } catch (error) {
        console.error('Failed to fetch or load buylists:', error);
        message.error('Failed to initialize buylists.');
      } finally {
        setLoading(false);
      }
    };
  
    initializeBuylists();
  }, [initialBuylistId, initialBuylistName]);
  
  // Update effects when cards change - Restored from old version
  useEffect(() => {
    // This effect runs every time the `cards` array changes.
    setSavedBuylists(current =>
      current.map(buylist =>
        buylist.id === selectedBuylist?.buylistId
          ? { ...buylist, cards_count: cards.length }
          : buylist
      )
    );
    
    // console.log('Table items have changed. New cards:', cards);
  }, [cards, selectedBuylist?.buylistId]);
  
  // Column definitions for cards table
  const cardColumns = useMemo(() => {
    // Use standard table columns for cards with search props and click handler for card details
    const baseColumns = getStandardTableColumns(
      (record) => handleCardClick(record),
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
      const response = await api.get('/buylists');
      if (response.data) {
        setSavedBuylists(response.data);
        setSelectedBuylist({ buylistId: response.data[0].id, name: response.data[0].name });
        setLoadedBuylistName(response.data[0]?.name);
      }
    } catch (error) {
      console.error('Debug: Failed to fetch saved buylists', error);
      message.error('Failed to fetch saved buylists');
    }
  };

  const handleLoadBuylist = async (buylist) => {
    setLoading(true);
    try {
      const response = await api.get(`/buylists/${buylist.id}`);
  
      const cardsData = Array.isArray(response.data) ? response.data : [];
  
      setCards(cardsData);
      setSelectedBuylist({ buylistId: buylist.id, name: buylist.name });
      setLoadedBuylistName(buylist.name);
  
      // Sync cards_count immediately
      setSavedBuylists(prev =>
        prev.map(b =>
          b.id === buylist.id ? { ...b, cards_count: cardsData.length } : b
        )
      );
  
      message.success(`Buylist "${buylist.name}" loaded successfully.`);
    } catch (error) {
      console.error('Failed to load buylist:', error);
      message.error('Failed to load buylist.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveBuylist = async () => {
    setErrorCards([]);
    if (!selectedBuylist?.buylistId || !selectedBuylist?.name) {
      message.error('Buylist ID and name are required.');
      return;
    }
  
    try {
      const response = await api.put(`/buylists/${selectedBuylist?.buylistId}/rename`, {
        name: selectedBuylist?.name
      });
  
      const updatedBuylist = response.data;
  
      // Update saved buylists in state:
      setSavedBuylists(prev =>
        prev.map(buylist =>
          buylist.id === selectedBuylist?.buylistId ? { ...buylist, name: updatedBuylist.name } : buylist
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
      selectedBuylist?.name.trim() !== loadedBuylistName.trim()
          ? selectedBuylist?.name.trim() || "Untitled Buylist"
          : "Untitled Buylist";

    try {
      const response = await api.post("/buylists", {
          name: trimmedBuylistName,
          cards: []
      });

      const newBuylist = response.data;

      setSelectedBuylist({ buylistId: newBuylist.id, name: newBuylist.name });
      setLoadedBuylistName(newBuylist.name);

      setCards([]);
      setErrorCards([]);
      setCardText("");

      // Update Saved Buylists list immediately
      setSavedBuylists((prevBuylists) => [
          ...prevBuylists,
          { buylistId: newBuylist.id, name: newBuylist.name }
      ]);

      message.success(`New buylist "${newBuylist.name}" created.`);
    } catch (error) {
      message.error("Failed to create a new buylist.");
      console.error("Error creating new buylist:", error);
    }
  };

  const handleDeleteBuylist = useCallback((buylistId) => {
    deleteBuylistMutation.mutate({ buylistId });
  }, [deleteBuylistMutation, selectedBuylist?.buylistId]);
  
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
        const response = await api.get(`/card_suggestions?query=${query}`);
        // console.log('Suggestions received:', response.data);
        setSuggestions(response.data.map(name => ({ value: name })));
      } catch (error) {
        console.error('Error fetching suggestions:', error);
        setSuggestions([]);
      }
    } else {
      setSuggestions([]);
    }
  };

  const handleSelectCard = useCallback(async (value) => {
    // Generate a temporary client-side ID
    const clientSideId = `temp-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    
    // Create the new card object
    const newCard = {
      id: clientSideId,
      name: value,
      quantity: 1,
      set_name: '',
      quality: 'NM',
      language: 'English',
      version: 'Standard',
      foil: false
    };
    
    // Optimistically update UI first
    setCards(prevCards => [...prevCards, newCard]);
    setSuggestions([]);
    
    try {
      // Save the card to the server
      const response = await api.post(`/buylists/${selectedBuylist?.buylistId}/cards`,  {
        cards: [{
          name: value,
          quantity: 1,
          quality: 'NM',
          language: 'English',
          set_name: '',
          set_code: '',
          version: 'Standard',
          foil: false
        }]
      });
      
      // If successful, update the card with the server-provided ID
      if (response.data && response.data.addedCards && response.data.addedCards.length > 0) {
        const serverCard = response.data.addedCards[0];
        
        // Replace the temporary card with the server version
        setCards(prevCards => prevCards.map(card => 
          card.id === clientSideId ? { ...serverCard, id: serverCard.id } : card
        ));
        
        // console.log('Card added successfully:', serverCard);
        message.success('Card(s) added successfully.');
      }
    } catch (error) {
      console.error('Error adding card:', error);
      message.error(`Failed to add card: ${error.message}`);
      
      // Remove the card from UI if the API call fails
      setCards(prevCards => prevCards.filter(card => card.id !== clientSideId));
    }
  }, [selectedBuylist?.buylistId, setCards]);
  
  const handleModalClose = () => {
    setIsModalVisible(false);
    setSelectedCard(null);
    setFetchedCard(null);
    setModalMode('view');
  };

  const GenericFetchCard= async (card) =>{
    setFetchedCard(null);
    setIsModalVisible(true);
    setIsModalLoading(true); 
    try {
      const data = await fetchCard({
        name: card.name,
        set_code: card.set || card.set_code || '',
        language: card.language || 'en',
        version: card.version || 'Standard'
      });
      const enrichedCard = {
        ...card,
        ...data,
      };
      setFetchedCard(enrichedCard);
      // console.log("card incoming props:", card);
      // console.log("response.data incoming props:", response.data);
    } catch (error) {
      // console.error('Error fetching card:', error);
      message.error(`Failed to fetch card details: ${error.message}`);
      setIsModalVisible(false);    // Close modal on error
    } finally {
      setIsModalLoading(false);    // Stop spinner
    }
  }

  // Handlers for card view/edit
  const handleCardClick = useCallback(async (card) => {
    setSelectedCard(card);
    setModalMode('view');
    GenericFetchCard(card)
  });
  
  const handleEditCard = useCallback(async (card) => {
    setSelectedCard(card);
    setModalMode('edit');
    GenericFetchCard(card)
  });
  
  const handleSaveEdit = useCallback(async (updatedCard) => {
    setErrorCards([]);
    // console.log('1. Updated card:', updatedCard);
  
    const payload = {
      ...updatedCard,
      buylistid: selectedBuylist?.buylistId,
      quantity: updatedCard.quantity || 1,
      foil: updatedCard.foil || false,

    };

    try {
      const response = await api.put(`/buylist/cards/${updatedCard.id}`, payload);
  
      if (!response.data) {
        throw new Error('No data received from update');
      }
  
      setCards((prevCards) =>
        prevCards.map((card) =>
          card.id === updatedCard.id ? { ...card, ...updatedCard } : card
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
  }, [setCards, handleModalClose]);
  
  const handleDeleteCard = useCallback((cardId) => {
    const cardToDelete = cards.find(card => card.id === cardId);
    if (!cardToDelete) {
      message.error('Card not found');
      return;
    }
    deleteCardMutation.mutate({
      id: cardId,
      cardData: {
        name: cardToDelete.name,
        quantity: cardToDelete.quantity || 1
      }
    });
  }, [deleteCardMutation, cards]);
  
  // Handler for bulk deletion 
  const handleBulkDelete = useCallback(() => {
    if (selectedCardIds.size === 0) {
      message.warning('No cards selected for deletion.');
      return;
    }

    const cardsToDelete = cards
      .filter(card => selectedCardIds.has(card.id))
      .map(card => ({
        name: card.name,
        quantity: card.quantity || 1
      }));

    // Optimistically update the UI
    setCards(prev => prev.filter(card => !selectedCardIds.has(card.id)));
    setSelectedCardIds(new Set());

    bulkDeleteCardsMutation.mutate({ cardsToDelete });
  }, [selectedCardIds, cards, selectedBuylist?.buylistId]);

  const debouncedFetchSuggestions = debounce(fetchSuggestions, 300);
  
  return (
    <div className={`card-management ${theme}`}>
      <Title level={2}>Buylist Management</Title>
      
      {/* Restored UI Layout from old version - Three column layout */}
      <div style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 24 }}>
        {/* Column 1: Card search and import */}
        <div style={{ flex: '1 1 150px', minWidth: '150px', marginRight: '16px' }}>
          {selectedBuylist?.buylistId && <Title level={4} style={{ marginTop: 0 }}>Current buylist: {selectedBuylist?.name}</Title>}
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
              buylistId={selectedBuylist?.buylistId}
              onCardsAdded={handleCardImport}
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
            value={selectedBuylist?.name}
            onChange={(e) => setSelectedBuylist(prev => ({
              ...prev,
              name: e.target.value
            }))}
            
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
                style={item.id === selectedBuylist?.buylistId ? { fontWeight: 'bold' } : {}}
              >
                <Button
                  type="link"
                  icon={<FolderOpenOutlined />}
                  onClick={() => handleLoadBuylist(item)}
                  style={{ marginRight: 8 }}
                >
                  Load
                </Button>
                <Popconfirm
                  title="Are you sure you want to delete this buylist?"
                  okText="Yes"
                  cancelText="No"
                  onConfirm={() => handleDeleteBuylist(item.id)}
                >
                  <Button
                    type="link"
                    danger
                    icon={<DeleteOutlined />}
                  >
                    Delete
                  </Button>
                </Popconfirm>

                {item.name} {(item.id === selectedBuylist?.buylistId)
                  ? `(${cards.length})`
                  : (item.cards_count !== undefined ? `(${item.cards_count})` : '')}
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
          <Popconfirm
          title={`Are you sure you want to delete ${selectedCardIds.size} card(s)?`}
          okText="Yes"
          cancelText="No"
          onConfirm={handleBulkDelete}
        >
          <Button danger icon={<DeleteOutlined />}>
            Delete Selected ({selectedCardIds.size})
          </Button>
        </Popconfirm>
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
        onRowClick={handleCardClick}
        onChange={handleTableChange}
      />
      
      {/* Card Detail Modal */}
      <Modal
        key={selectedCard?.id}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={
          modalMode === 'edit'
            ? [
                <Button key="close" onClick={() => setIsModalVisible(false)}>
                  Close
                </Button>,
                <Button
                  key="save"
                  type="primary"
                  onClick={() => {
                    if (pendingSelection) handleSaveEdit(pendingSelection);
                  }}
                >
                  Save
                </Button>,
              ]
            : [
                <Button key="close" onClick={() => setIsModalVisible(false)}>
                  Close
                </Button>,
              ]
        }        
        width={800}
        destroyOnClose
      >
          <Spin spinning={isModalLoading} tip="Loading card details...">
          {cardData ? (
          <ScryfallCardView 
            key={`${selectedCard?.id}-${cardData.id}`}
            cardData={cardData}
            mode={modalMode}
            onSave={handleSaveEdit}
            onChange={setPendingSelection}
          />
          ) : (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <p>No card data available</p>
            </div>
          )}
        </Spin>
      </Modal>
    </div>
  );
};

export default BuylistManagement;