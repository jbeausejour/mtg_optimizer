import React, { useState, useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { Table, Spin, Card, Tag, Typography, Space, Button, Modal, message, Popconfirm, Input } from 'antd';
import { CheckCircleOutlined, WarningOutlined, DeleteOutlined, SearchOutlined, ClearOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import ScryfallCardView from '../components/Shared/ScryfallCardView';
import api from '../utils/api';
import ColumnSelector from '../components/ColumnSelector';
import { ExportOptions } from '../utils/exportUtils';
import { 
  getColumnSearchProps, 
  getStandardPagination
} from '../utils/tableConfig';
import EnhancedTable from '../components/EnhancedTable';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';

const { Title, Text } = Typography;

const Results = ({ userId }) => {
  const [selectedResult, setSelectedResult] = useState(null);
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const { theme } = useTheme();
  const [isLoading, setIsLoading] = useState(false);
  const queryClient = useQueryClient();
  
  // Use enhanced table handler for consistent behavior
  const {
    filteredInfo,
    sortedInfo,
    pagination,
    selectedIds: selectedResultIds,
    setSelectedIds: setSelectedResultIds,
    searchInput,
    visibleColumns,
    handleTableChange,
    handleSearch,
    handleReset,
    handleResetAllFilters,
    handleColumnVisibilityChange
  } = useEnhancedTableHandler({
    visibleColumns: [
      'id', 'created_at', 'buylist_name', 'stats', 'best_solution', 'iteration', 'status', 'action'
    ]
  }, 'optimization_results_table');

  // Use React Query for fetching optimization results
  const { 
    data: optimizationResults = [], 
    isLoading: loading 
  } = useQuery(
    ['optimizations', userId], 
    () => api.get('/results', { params: { user_id: userId } })
      .then(res => res.data),
    { staleTime: 300000 } // 5 minutes
  );

  // Delete mutation for optimization results
  const deleteOptimizationMutation = useMutation(
    (resultId) => api.delete(`/results/${resultId}`, { params: { user_id: userId } }),
    {
      // Optimistic update - remove the item immediately from UI
      onMutate: async (resultId) => {
        // Cancel any outgoing refetches
        await queryClient.cancelQueries(['optimizations', userId]);
        
        // Save the previous value
        const previousResults = queryClient.getQueryData(['optimizations', userId]);
        
        // Optimistically update to the new value
        queryClient.setQueryData(['optimizations', userId], old => 
          old.filter(result => result.id !== resultId)
        );
        
        // Return the previous value in case of rollback
        return { previousResults };
      },
      onError: (err, resultId, context) => {
        // Roll back to the previous value if there's an error
        queryClient.setQueryData(['optimizations', userId], context.previousResults);
        message.error('Failed to delete optimization.');
      },
      onSuccess: (_, resultId) => {
        message.success('Optimization deleted successfully');
        // If the deleted result is currently selected, deselect it
        if (selectedResult && selectedResult.id === resultId) {
          setSelectedResult(null);
        }
      },
      onSettled: () => {
        // Always refetch after error or success
        queryClient.invalidateQueries(['optimizations', userId]);
      }
    }
  );

  // Use React Query for fetching card details
  const fetchCardMutation = useMutation(
    (params) => api.get('/fetch_card', { params }),
    {
      onSuccess: (response) => {
        if (!response.data?.scryfall) {
          throw new Error('Invalid card data received');
        }
        setCardData(response.data.scryfall);
        setIsModalVisible(true);
      },
      onError: (error) => {
        console.error('Error fetching card:', error);
        message.error(`Failed to fetch card details: ${error.message}`);
      },
      onSettled: () => {
        setIsLoading(false);
      }
    }
  );

  // Define handleCardClick
  const handleCardClick = useCallback(async (card) => {
    setSelectedCard(card);
    setIsLoading(true);
    
    const params = {
      name: card.name,
      set: card.set_code || card.set_name,
      language: card.language || 'English',
      version: card.version || 'Normal',
      user_id: userId
    };
    
    fetchCardMutation.mutate(params);
  }, [fetchCardMutation, userId]);

  // Define handleDelete
  const handleDelete = useCallback((resultId) => {
    deleteOptimizationMutation.mutate(resultId);
  }, [deleteOptimizationMutation]);

  const formatDate = useCallback((dateString) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'N/A';
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'N/A';
    }
  }, []);

  // Handle bulk deletion
  const handleBulkDelete = useCallback(() => {
    if (selectedResultIds.size === 0) {
      message.warning('No optimizations selected for deletion.');
      return;
    }
  
    Modal.confirm({
      title: `Are you sure you want to delete ${selectedResultIds.size} selected optimization(s)?`,
      content: 'This action cannot be undone.',
      okText: 'Yes, delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          // Store count before clearing for message
          const count = selectedResultIds.size;
          
          // Create an array of deletion promises
          const deletionPromises = Array.from(selectedResultIds).map(id => 
            deleteOptimizationMutation.mutateAsync(id)
          );
          
          // Wait for all deletions to complete
          await Promise.all(deletionPromises);
          
          // Clear selection and show success
          setSelectedResultIds(new Set());
          message.success(`Successfully deleted ${count} optimization(s).`);
          
          // Invalidate after everything is done
          queryClient.invalidateQueries(['optimizations', userId]);
        } catch (error) {
          console.error('Bulk deletion error:', error);
          message.error('Failed to delete some or all selected optimizations.');
          // Invalidate to get back to a consistent state
          queryClient.invalidateQueries(['optimizations', userId]);
        }
      }
    });
  }, [selectedResultIds, deleteOptimizationMutation, setSelectedResultIds, userId]);

  // Define columns for the results table
  const columns = useMemo(() => [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
      sorter: (a, b) => a.id - b.id,
      sortOrder: sortedInfo.columnKey === 'id' && sortedInfo.order,
      ...getColumnSearchProps('id', searchInput, filteredInfo, 'Search by ID', handleSearch, handleReset),
    },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: text => formatDate(text),
      sorter: (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0),
      sortOrder: sortedInfo.columnKey === 'created_at' && sortedInfo.order,
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <Input
            type="date"
            placeholder="Search date"
            value={selectedKeys[0]}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            onPressEnter={() => handleSearch(selectedKeys, confirm, 'created_at')}
            style={{ width: 188, marginBottom: 8, display: 'block' }}
            ref={el => (searchInput.current['created_at'] = el)}
          />
          <Space>
            <Button
              type="primary"
              onClick={() => handleSearch(selectedKeys, confirm, 'created_at')}
              icon={<SearchOutlined />}
              size="small"
              style={{ width: 90 }}
            >
              Search
            </Button>
            <Button
              onClick={() => handleReset(clearFilters, 'created_at')}
              size="small"
              style={{ width: 90 }}
            >
              Reset
            </Button>
          </Space>
        </div>
      ),
      onFilter: (value, record) => {
        if (!record.created_at) return false;
        const recordDate = new Date(record.created_at).toISOString().split('T')[0];
        return recordDate === value;
      },
      filteredValue: filteredInfo.created_at || null,
    },
    {
      title: 'Buylist',
      dataIndex: 'buylist_name',
      key: 'buylist_name',
      render: (text) => text || <Tag color="red">Unknown</Tag>,
      sorter: (a, b) => (a.buylist_name || '').localeCompare(b.buylist_name || ''),
      sortOrder: sortedInfo.columnKey === 'buylist_name' && sortedInfo.order,
      ...getColumnSearchProps('buylist_name', searchInput, filteredInfo, 'Search buylist', handleSearch, handleReset),
    },
    {
      title: 'Stats',
      key: 'stats',
      filters: [
        { text: 'Low Cards (<10)', value: 'low' },
        { text: 'Medium Cards (10-30)', value: 'medium' },
        { text: 'High Cards (>30)', value: 'high' },
      ],
      onFilter: (value, record) => {
        const cardCount = record.cards_scraped || 0;
        if (value === 'low') return cardCount < 10;
        if (value === 'medium') return cardCount >= 10 && cardCount <= 30;
        if (value === 'high') return cardCount > 30;
        return true;
      },
      filteredValue: filteredInfo.stats || null,
      render: (_, record) => (
        <Space>
          <Tag color="blue">{`${record.sites_scraped || 0} Sites`}</Tag>
          <Tag color="purple">{`${record.cards_scraped || 0} Cards`}</Tag>
        </Space>
      ),
    },
    {
      title: 'Best Solution',
      key: 'best_solution',
      filters: [
        { text: 'Complete', value: 'complete' },
        { text: 'Partial', value: 'partial' },
        { text: 'Failed', value: 'failed' },
      ],
      onFilter: (value, record) => {
        const bestSolution = record.solutions?.find(s => s.is_best_solution);
        if (!bestSolution) return value === 'failed';
        
        const completeness = bestSolution.missing_cards_count === 0;
        if (value === 'complete') return completeness;
        if (value === 'partial') return !completeness;
        return false;
      },
      filteredValue: filteredInfo.best_solution || null,
      render: (_, record) => {
        const bestSolution = record.solutions?.find(s => s.is_best_solution);
        if (!bestSolution) return <Tag color="red">No solution</Tag>;

        const completeness = bestSolution.missing_cards_count === 0;
        const percentage = ((bestSolution.nbr_card_in_solution / bestSolution.total_qty) * 100).toFixed(1);

        return (
          <Space>
            <Tag color="blue">{`${bestSolution.number_store} Stores`}</Tag>
            <Tag color={completeness ? 'green' : 'orange'}>
              {completeness ? 'Complete' : `${percentage}%`}
            </Tag>
            <Text>${bestSolution.total_price.toFixed(2)}</Text>
          </Space>
        );
      },
    },
    {
      title: 'Iteration',
      key: 'iteration',
      sorter: (a, b) => {
        const iterationA = a.solutions?.filter(s => !s.is_best_solution).length || 0;
        const iterationB = b.solutions?.filter(s => !s.is_best_solution).length || 0;
        return iterationA - iterationB;
      },
      sortOrder: sortedInfo.columnKey === 'iteration' && sortedInfo.order,
      render: (_, record) => {
        const iterationCount = record.solutions?.filter(s => !s.is_best_solution).length;
        if (!iterationCount) return <Tag color="red">No iteration</Tag>;

        return (
          <Space>
            <Tag color="blue">{`Iteration ${iterationCount}`}</Tag>
          </Space>
        );
      },
    },
    {
      title: 'Status',
      key: 'status',
      filters: [
        { text: 'Success', value: 'Completed' },
        { text: 'Failed', value: 'Failed' },
      ],
      onFilter: (value, record) => record.status === value,
      filteredValue: filteredInfo.status || null,
      render: (_, record) => {
        const bestSolution = record.solutions?.find(s => s.is_best_solution);
        if (!bestSolution) return <Tag color="red">Failed</Tag>;
        
        if (record.status === 'Completed') {
          return <Tag color="green" icon={<CheckCircleOutlined />}>Success</Tag>;
        }
        
        return <Tag color="red" icon={<WarningOutlined />}>{record.status}</Tag>;
      },
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Popconfirm
          title="Are you sure you want to delete this optimization?"
          onConfirm={(e) => {
            if (e) e.stopPropagation();
            handleDelete(record.id);
          }}
          okText="Yes"
          cancelText="No"
          onCancel={(e) => e.stopPropagation()}
        >
          <Button 
            type="link" 
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => e.stopPropagation()}
          >
            Delete
          </Button>
        </Popconfirm>
      ),
    },
  ], [
    filteredInfo, 
    sortedInfo, 
    handleSearch, 
    handleReset, 
    handleDelete, 
    formatDate,
    searchInput
  ]);

  const handleModalClose = useCallback(() => {
    setIsModalVisible(false);
    setSelectedCard(null);
    setCardData(null);
  }, []);

  if (loading) return <Spin size="large" />;

  return (
    <div className={`results section ${theme}`}>
      <Title level={2}>Optimization History</Title>
      {selectedResult ? (
        <>
          <Button 
            type="link" 
            onClick={() => {
              setSelectedResult(null);
              // Reset pagination, filtering and sorting when going back
              handleResetAllFilters();
            }} 
            className="mb-4"
          >
            ← Back to History
          </Button>
          <OptimizationSummary 
            result={selectedResult}
            onCardClick={handleCardClick}
          />
        </>
      ) : (
        <Card>
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
            <Space style={{ marginBottom: 16 }}>
              <ColumnSelector 
                columns={columns}
                visibleColumns={visibleColumns}
                onColumnToggle={handleColumnVisibilityChange}
                persistKey="results_columns"
              />
              <ExportOptions 
                dataSource={optimizationResults} 
                columns={columns} 
                filename="optimization_results_export"
              />
              <Button
                onClick={handleResetAllFilters}
                icon={<ClearOutlined />}
              >
                Reset All Filters
              </Button>
              {selectedResultIds.size > 0 && (
                <Button danger onClick={handleBulkDelete} icon={<DeleteOutlined />}>
                  Delete Selected ({selectedResultIds.size})
                </Button>
              )}
            </Space>
          </div>

          <EnhancedTable
            dataSource={optimizationResults}
            columns={columns.filter(col => visibleColumns.includes(col.key))}
            rowKey="id"
            onChange={handleTableChange}
            pagination={pagination}
            rowSelectionEnabled={true}
            selectedIds={selectedResultIds}
            onSelectionChange={setSelectedResultIds}
            onRowClick={(record) => setSelectedResult(record)}
            persistStateKey="results_table"
          />
        </Card>
      )}

      <Modal
        title={selectedCard?.name}
        open={isModalVisible}
        onCancel={handleModalClose}
        width={800}
        footer={null}
      >
        {isLoading ? (
          <div className="text-center p-4">
            <Spin size="large" />
            <Text className="mt-4">Loading card details...</Text>
          </div>
        ) : cardData ? (
          <ScryfallCardView cardData={cardData} mode="view" />
        ) : (
          <div className="text-center p-4">
            <Text>No card data available</Text>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Results;