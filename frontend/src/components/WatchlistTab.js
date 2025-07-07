import React, { useState, useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Card, 
  Typography, 
  Button, 
  Space, 
  Modal, 
  Form, 
  AutoComplete,
  Select,
  InputNumber,
  Popconfirm,
  Tag,
  Tooltip,
  Alert,
  Divider,
  Input
} from 'antd';
import { 
  PlusOutlined, 
  DeleteOutlined, 
  ClearOutlined,
  DollarOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  EyeOutlined,
  SearchOutlined
} from '@ant-design/icons';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';
import { useApiWithNotifications } from '../utils/useApiWithNotifications';
import { useNotification } from '../utils/NotificationContext';
import EnhancedTable from '../components/EnhancedTable';
import ColumnSelector from '../components/ColumnSelector';
import api from '../utils/api';
import debounce from 'lodash/debounce';

const { Title, Text } = Typography;
const { Option } = Select;

const WatchlistTab = ({ onCardClick }) => {
  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [selectedWatchlistItem, setSelectedWatchlistItem] = useState(null);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const { messageApi, notificationApi } = useNotification();
  const { deleteWithNotifications } = useApiWithNotifications();

  // Autocomplete state - using your existing system
  const [cardSearchValue, setCardSearchValue] = useState('');
  const [suggestions, setCardSuggestions] = useState([]);
  const [selectedCardName, setSelectedCardName] = useState('');
  const [availableSets, setAvailableSets] = useState([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [isLoadingSets, setIsLoadingSets] = useState(false);

  // Enhanced table handler for watchlist
  const {
    filteredInfo,
    sortedInfo,
    pagination,
    selectedIds,
    setSelectedIds,
    searchInput,
    visibleColumns,
    handleTableChange,
    handleSearch,
    handleReset,
    handleResetAllFilters,
    resetSelection,
    handleColumnVisibilityChange
  } = useEnhancedTableHandler({
    visibleColumns: [
      'card_name', 'set_code', 'target_price', 'current_market', 
      'best_deal', 'savings', 'last_checked', 'actions'
    ]
  }, 'watchlist_table');

  // Fetch watchlist data
  const { data: watchlist = [], isLoading: watchlistLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: () => api.get('/watchlist').then(res => res.data),
    staleTime: 60000, // Cache for 1 minute
    refetchInterval: 300000 // Auto-refresh every 5 minutes
  });

  // Fetch price alerts
  const { data: alerts = [], isLoading: alertsLoading } = useQuery({
    queryKey: ['watchlist-alerts'],
    queryFn: () => api.get('/watchlist/alerts').then(res => res.data),
    staleTime: 60000
  });

  // Card suggestions using your existing API
  const fetchSuggestions = async (query) => {
    if (query.length > 2) {
      try {
        const response = await api.get(`/card/suggestions?query=${query}`);
        // console.log('Suggestions received:', response.data);
        setCardSuggestions(response.data.map(name => ({ value: name })));
      } catch (error) {
        console.error('Error fetching suggestions:', error);
        setCardSuggestions([]);
      }
    } else {
      setCardSuggestions([]);
    }
  };

  // Fetch available sets for selected card from Scryfall data
  const fetchAvailableSets = useCallback(async (cardName) => {
    if (!cardName) {
      setAvailableSets([]);
      return;
    }

    setIsLoadingSets(true);
    try {
      const response = await api.get(`/card/${encodeURIComponent(cardName)}/sets`);
      setAvailableSets(response.data || []);
      
      if (response.data && response.data.length > 0) {
        messageApi.success(`Found ${response.data.length} set(s) for ${cardName}`);
      } else {
        messageApi.warning('No sets found for this card');
      }
    } catch (error) {
      console.error('Error fetching available sets:', error);
      setAvailableSets([]);
      messageApi.error('Could not load available sets for this card');
    } finally {
      setIsLoadingSets(false);
    }
  }, [messageApi]);

  // Handle card name search - using your existing pattern
  const handleSuggestionSearch = (value) => {
    
    setCardSearchValue(value);
    debouncedFetchSuggestions(value);
  };

  // Handle card name selection
  const handleCardNameSelect = useCallback((value, option) => {
    setSelectedCardName(value);
    setCardSearchValue(value);
    form.setFieldsValue({ card_name: value });
    
    // Fetch available sets for this card from Scryfall
    fetchAvailableSets(value);
    
    // Clear set selection when card changes
    form.setFieldsValue({ set_code: undefined });
  }, [form, fetchAvailableSets]);

  // Add to watchlist mutation
  const addToWatchlistMutation = useMutation({
    mutationFn: (data) => api.post('/watchlist', data),
    onSuccess: () => {
      queryClient.invalidateQueries(['watchlist']);
      setIsAddModalVisible(false);
      form.resetFields();
      setCardSearchValue('');
      setSelectedCardName('');
      setAvailableSets([]);
      setCardSuggestions([]);
      messageApi.success('Card added to watchlist');
    },
    onError: (err) => {
      messageApi.error(err.response?.data?.error || 'Failed to add card to watchlist');
    }
  });

  // Remove from watchlist mutation
  const removeFromWatchlistMutation = useMutation({
    mutationFn: (id) => api.delete(`/watchlist/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries(['watchlist']);
      messageApi.success('Card removed from watchlist');
    },
    onError: (err) => {
      messageApi.error(err.response?.data?.error || 'Failed to remove card from watchlist');
    }
  });

  // Update target price mutation
  const updateTargetPriceMutation = useMutation({
    mutationFn: ({ id, target_price }) => api.put(`/watchlist/${id}`, { target_price }),
    onSuccess: () => {
      queryClient.invalidateQueries(['watchlist']);
      messageApi.success('Target price updated');
    },
    onError: (err) => {
      messageApi.error(err.response?.data?.error || 'Failed to update target price');
    }
  });

  const handleAddToWatchlist = useCallback(async (values) => {
    try {
      addToWatchlistMutation.mutate(values);
    } catch (err) {
      messageApi.error('Failed to add card to watchlist');
    }
  }, [addToWatchlistMutation, messageApi]);

  const handleBulkDelete = useCallback(async () => {
    if (selectedIds.size === 0) {
      messageApi.warning('No items selected for deletion.');
      return;
    }

    await deleteWithNotifications(
      async () => {
        const idList = Array.from(selectedIds);
        await api.delete('/watchlist/delete-many', {
          data: { ids: idList }
        });
        return { count: idList.length };
      },
      'watchlist items',
      {
        loadingMessage: `Removing ${selectedIds.size} item(s) from watchlist...`,
        onSuccess: () => {
          setSelectedIds(new Set());
          queryClient.invalidateQueries(['watchlist']);
        },
        onError: () => {
          queryClient.invalidateQueries(['watchlist']);
        }
      }
    );
  }, [selectedIds, setSelectedIds, queryClient, deleteWithNotifications, messageApi]);

  // Handle modal cancel
  const handleModalCancel = useCallback(() => {
    setIsAddModalVisible(false);
    form.resetFields();
    setCardSearchValue('');
    setSelectedCardName('');
    setAvailableSets([]);
    setCardSuggestions([]);
  }, [form]);

  const formatPrice = (price) => {
    if (!price) return '—';
    return `$${parseFloat(price).toFixed(2)}`;
  };

  const calculateSavings = (marketPrice, bestPrice) => {
    if (!marketPrice || !bestPrice) return null;
    const savings = marketPrice - bestPrice;
    const percentage = ((savings / marketPrice) * 100).toFixed(1);
    return { amount: savings, percentage };
  };

  const renderSavingsTag = (savings) => {
    if (!savings || savings.amount <= 0) {
      return <Tag color="default">No savings</Tag>;
    }
    
    const color = savings.amount > 5 ? 'green' : savings.amount > 2 ? 'gold' : 'blue';
    return (
      <Tag color={color} icon={<ArrowDownOutlined />}>
        Save ${savings.amount.toFixed(2)} ({savings.percentage}%)
      </Tag>
    );
  };

  const watchlistColumns = useMemo(() => {
    const baseColumns = [
      {
        title: 'Card Name',
        dataIndex: 'card_name',
        key: 'card_name',
        sorter: (a, b) => (a.card_name || '').localeCompare(b.card_name || ''),
        sortOrder: sortedInfo.columnKey === 'card_name' && sortedInfo.order,
        render: (text, record) => (
          <Button 
            type="link" 
            onClick={() => onCardClick && onCardClick(record)}
            style={{ padding: 0, height: 'auto', fontWeight: 'bold' }}
          >
            {text}
          </Button>
        ),
      },
      {
        title: 'Set',
        dataIndex: 'set_code',
        key: 'set_code',
        sorter: (a, b) => (a.set_code || '').localeCompare(b.set_code || ''),
        render: (text) => text ? (
          <Tag color="blue">{text.toUpperCase()}</Tag>
        ) : (
          <Tag color="default">Any Set</Tag>
        ),
      },
      {
        title: 'Target Price',
        dataIndex: 'target_price',
        key: 'target_price',
        sorter: (a, b) => (a.target_price || 0) - (b.target_price || 0),
        render: (text, record) => (
          <Tooltip title="Click to edit">
            <Button 
              type="text" 
              size="small"
              onClick={() => {
                setSelectedWatchlistItem(record);
                // Could open inline editor or modal
              }}
            >
              {formatPrice(text)}
            </Button>
          </Tooltip>
        ),
      },
      {
        title: 'Market Price',
        dataIndex: 'current_market_price',
        key: 'current_market',
        sorter: (a, b) => (a.current_market_price || 0) - (b.current_market_price || 0),
        render: (text, record) => (
          <Space direction="vertical" size="small">
            <Text strong>{formatPrice(text)}</Text>
            {record.mtgstocks_url && (
              <Button 
                type="link" 
                size="small" 
                icon={<EyeOutlined />}
                href={record.mtgstocks_url}
                target="_blank"
              >
                MTGStocks
              </Button>
            )}
          </Space>
        ),
      },
      {
        title: 'Best Deal',
        dataIndex: 'best_price',
        key: 'best_deal',
        sorter: (a, b) => (a.best_price || 0) - (b.best_price || 0),
        render: (text, record) => (
          <Space direction="vertical" size="small">
            <Text strong>{formatPrice(text)}</Text>
            {record.best_price_site && (
              <Text type="secondary" style={{ fontSize: '12px' }}>
                at {record.best_price_site}
              </Text>
            )}
          </Space>
        ),
      },
      {
        title: 'Savings',
        key: 'savings',
        render: (_, record) => {
          const savings = calculateSavings(record.current_market_price, record.best_price);
          return renderSavingsTag(savings);
        },
        sorter: (a, b) => {
          const savingsA = calculateSavings(a.current_market_price, a.best_price);
          const savingsB = calculateSavings(b.current_market_price, b.best_price);
          return (savingsA?.amount || 0) - (savingsB?.amount || 0);
        },
      },
      {
        title: 'Last Checked',
        dataIndex: 'last_checked',
        key: 'last_checked',
        sorter: (a, b) => new Date(a.last_checked || 0) - new Date(b.last_checked || 0),
        render: (text) => {
          if (!text) return '—';
          const date = new Date(text);
          const now = new Date();
          const diffHours = Math.floor((now - date) / (1000 * 60 * 60));
          
          if (diffHours < 1) return 'Just now';
          if (diffHours < 24) return `${diffHours}h ago`;
          return date.toLocaleDateString();
        },
      },
      {
        title: 'Actions',
        key: 'actions',
        render: (_, record) => (
          <Space>
            <Popconfirm
              title="Remove from watchlist?"
              onConfirm={() => removeFromWatchlistMutation.mutate(record.id)}
            >
              <Button 
                type="text" 
                danger 
                icon={<DeleteOutlined />} 
                size="small"
              />
            </Popconfirm>
          </Space>
        ),
      }
    ];
    
    return baseColumns.filter(col => visibleColumns.includes(col.key));
  }, [sortedInfo, visibleColumns, onCardClick, removeFromWatchlistMutation]);

  const activeAlerts = alerts.filter(alert => 
    alert.current_price <= alert.target_price || 
    (alert.percentage_difference && alert.percentage_difference >= 10)
  );

  const debouncedFetchSuggestions = debounce(fetchSuggestions, 300);

  return (
    <div>
      {/* Price Alerts Section */}
      {activeAlerts.length > 0 && (
        <Card style={{ marginBottom: 16 }}>
          <Title level={4}>🔔 Price Alerts</Title>
          {activeAlerts.map(alert => (
            <Alert
              key={alert.id}
              type="success"
              showIcon
              style={{ marginBottom: 8 }}
              message={
                <Space>
                  <Text strong>{alert.card_name}</Text>
                  <Text>available for {formatPrice(alert.current_price)}</Text>
                  <Text type="secondary">at {alert.site_name}</Text>
                  {alert.percentage_difference && (
                    <Tag color="green">
                      {alert.percentage_difference.toFixed(1)}% below market
                    </Tag>
                  )}
                </Space>
              }
              action={
                <Button size="small" type="primary">
                  View Deal
                </Button>
              }
            />
          ))}
        </Card>
      )}

      {/* Main Watchlist Table */}
      <Card>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
          <Space>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setIsAddModalVisible(true)}
            >
              Add to Watchlist
            </Button>
            <ColumnSelector 
              columns={watchlistColumns}
              visibleColumns={visibleColumns}
              onColumnToggle={handleColumnVisibilityChange}
              persistKey="watchlist_columns"
            />
            <Button onClick={handleResetAllFilters} icon={<ClearOutlined />}>
              Reset All Filters
            </Button>
          </Space>
          
          {selectedIds.size > 0 && (
            <Popconfirm
              title={`Remove ${selectedIds.size} selected item(s) from watchlist?`}
              onConfirm={handleBulkDelete}
            >
              <Button danger icon={<DeleteOutlined />}>
                Remove Selected ({selectedIds.size})
              </Button>
            </Popconfirm>
          )}
        </div>

        <EnhancedTable
          dataSource={watchlist}
          columns={watchlistColumns}
          exportFilename="watchlist_export"
          rowKey="id"
          loading={watchlistLoading}
          persistStateKey="watchlist_table"
          rowSelectionEnabled={true}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          onChange={handleTableChange}
          pagination={pagination}
        />
      </Card>

      {/* Enhanced Add to Watchlist Modal */}
      <Modal
        title="Add Card to Watchlist"
        open={isAddModalVisible}
        onCancel={handleModalCancel}
        footer={null}
        destroyOnClose
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleAddToWatchlist}
        >
          <Form.Item
            label="Card Name"
            name="card_name"
            rules={[{ required: true, message: 'Please select a card' }]}
          >
            <AutoComplete
              options={suggestions}
              onSearch={handleSuggestionSearch}
              onSelect={handleCardNameSelect}
              placeholder="Search for a card..."
              value={cardSearchValue}
              onChange={setCardSearchValue}
              style={{ width: '100%' }}
              notFoundContent={isLoadingSuggestions ? 'Searching...' : 'No cards found'}
              filterOption={false} // We handle filtering on the backend
            >
              <Input prefix={<SearchOutlined />} />
            </AutoComplete>
          </Form.Item>
          
          <Form.Item
            label="Specific Set (Optional)"
            name="set_code"
            tooltip="Select a specific set where this card was printed. Leave empty to watch the card from any set."
          >
            <Select
              placeholder={isLoadingSets ? "Loading sets..." : "Select a specific set (optional)"}
              loading={isLoadingSets}
              allowClear
              disabled={!selectedCardName || isLoadingSets}
              notFoundContent={
                !selectedCardName ? 'Select a card first' :
                isLoadingSets ? 'Loading...' :
                availableSets.length === 0 ? 'No sets available' : null
              }
            >
              {availableSets.map(set => (
                <Option key={set.value} value={set.value}>
                  {set.label}
                </Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item
            label="Target Price Alert"
            name="target_price"
            tooltip="Get notified when the card drops below this price"
          >
            <InputNumber
              style={{ width: '100%' }}
              placeholder="0.00"
              min={0}
              step={0.01}
              prefix="$"
              formatter={value => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={value => value.replace(/\$\s?|(,*)/g, '')}
            />
          </Form.Item>
          
          <Divider />
          
          <div style={{ marginBottom: 16, padding: '12px', backgroundColor: '#f8f9fa', borderRadius: '6px' }}>
            <Text type="secondary" style={{ fontSize: '14px' }}>
              <strong>Note:</strong> If you select a specific set, price alerts will only trigger for that exact card+set combination. 
              Leave the set field empty to watch for the card from any set.
            </Text>
          </div>
          
          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={handleModalCancel}>
                Cancel
              </Button>
              <Button 
                type="primary" 
                htmlType="submit"
                loading={addToWatchlistMutation.isLoading}
                disabled={!selectedCardName}
              >
                Add to Watchlist
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default WatchlistTab;