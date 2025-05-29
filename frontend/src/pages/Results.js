import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient} from '@tanstack/react-query';
import { Spin, Card, Tag, Typography, Space, Button, Modal, message, Popconfirm, Input } from 'antd';

import { useLocation } from 'react-router-dom';

import { CheckCircleOutlined, WarningOutlined, DeleteOutlined, SearchOutlined, ClearOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import api from '../utils/api';
import ColumnSelector from '../components/ColumnSelector';
import { getColumnSearchProps, getStandardPagination } from '../utils/tableConfig';
import EnhancedTable from '../components/EnhancedTable';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';
import { useFetchScryfallCard } from '../hooks/useFetchScryfallCard';
import ScryfallCardView from '../components/Shared/ScryfallCardView';

const { Title, Text } = Typography;

const Results = () => {
  const { theme } = useTheme();
  const location = useLocation();
  const [selectedResult, setSelectedResult] = useState(null);
  const [selectedCard, setSelectedCard] = useState(null);
  const [modalMode, setModalMode] = useState('view');
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const queryClient = useQueryClient();
  const [cardData, setFetchedCard] = useState(null);
  const [hasShownSuccessMessage, setHasShownSuccessMessage] = useState(false);
  const {
    mutateAsync: fetchCard,
  } = useFetchScryfallCard();
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
  } = useQuery({
    queryKey: ['optimizations'],
    queryFn: () => api.get('/results').then(res => res.data),
    staleTime: 300000
  })
  
// Improved useEffect - add this to your Results.js component
useEffect(() => {
  // Only proceed if we came from optimization page and haven't shown message yet
  if (location.state?.fromOptimization && !hasShownSuccessMessage) {
    // Wait for data to be loaded and not empty
    if (!loading && optimizationResults && optimizationResults.length > 0) {
      const latestResult = optimizationResults[0]; // Assuming results are sorted by date desc
      setSelectedResult(latestResult);
      
      // Show success message only once
      message.success('🎉 Your latest optimization is ready! Results shown below.');
      setHasShownSuccessMessage(true);
      
      // Optional: Clear the location state to prevent re-triggering on subsequent visits
      window.history.replaceState({}, document.title);
    }
  }
}, [optimizationResults, location.state, loading, hasShownSuccessMessage]);

  
  const handleModalClose = () => {
    setIsModalVisible(false);
    setFetchedCard(null);
  };

  const handleCardClick = async (card) => {
    setSelectedCard(card);
    setModalMode('view');
    setFetchedCard(null);
    setIsModalVisible(true);
  
    try {
      const data = await fetchCard({
        name: card.name,
        set_code: card.set || card.set_code || '',
        language: card.language || 'en',
        version: card.version || 'Standard',
      });
      const enrichedCard = {
        ...card,
        ...data,
      };
      setFetchedCard(enrichedCard);
    } catch (err) {
      message.error('Failed to fetch card data');
      setIsModalVisible(false);    // Close modal on error
    } finally {
      setIsModalLoading(false);    // Stop spinner
    }
  };

  const handleSaveEdit = (updatedData) => {
    // console.log('[PriceTracker] Saved card data:', updatedData);
    setIsModalVisible(false);
  };

  const formatDate = (input) => {
    if (!input) return '—';
  
    try {
      const date = new Date(input);
      if (isNaN(date)) return input; // fallback for unparsable input
  
      const new_date = new Intl.DateTimeFormat('en-CA', {
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(date);
      return new_date;
    } catch (err) {
      console.error('Error formatting date:', err);
      return input;
    }
  };
  
  // Delete mutation for optimization results
  const deleteOptimizationMutation = useMutation({
    mutationFn: (resultId) => api.delete(`/results/${resultId}`),
    // Optimistic update - remove the item immediately from UI
    onMutate: async (resultId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries(['optimizations']);
      
      // Save the previous value
      const previousResults = queryClient.getQueryData(['optimizations']);
      
      // Optimistically update to the new value
      queryClient.setQueryData(['optimizations'], old => 
        old.filter(result => result.id !== resultId)
      );
      
      // Return the previous value in case of rollback
      return { previousResults };
    },
    onError: (err, resultId, context) => {
      // Roll back to the previous value if there's an error
      queryClient.setQueryData(['optimizations'], context.previousResults);
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
      queryClient.invalidateQueries(['optimizations']);
    }
  });
  
  // Define handleDelete
  const handleDelete = useCallback((resultId) => {
    deleteOptimizationMutation.mutate(resultId);
  }, [deleteOptimizationMutation]);

  // Handle bulk deletion
  const handleBulkDelete = useCallback(async () => {
    try {
      const count = selectedResultIds.size;
      const deletionPromises = Array.from(selectedResultIds).map(resultId =>
        deleteOptimizationMutation.mutateAsync(resultId)
      );
      await Promise.all(deletionPromises);
      setSelectedResultIds(new Set());
      message.success(`Successfully deleted ${count} result(s).`);
      queryClient.invalidateQueries(['results']);
    } catch (error) {
      console.error('Bulk deletion error:', error);
      message.error('Failed to delete some or all of the selected results.');
      queryClient.invalidateQueries(['results']);
    }
  }, [selectedResultIds, deleteOptimizationMutation, setSelectedResultIds, queryClient]);
  
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
              <Button
                onClick={handleResetAllFilters}
                icon={<ClearOutlined />}
              >
                Reset All Filters
              </Button>
              {selectedResultIds.size > 0 && (
                <Popconfirm
                title={`Are you sure you want to delete ${selectedResultIds.size} selected result(s)?`}
                okText="Yes"
                cancelText="No"
                onConfirm={handleBulkDelete}
                disabled={selectedResultIds.size === 0}
              >
                <Button danger icon={<DeleteOutlined />} disabled={selectedResultIds.size === 0}>
                  Delete Selected ({selectedResultIds.size})
                </Button>
              </Popconfirm>
              )}
            </Space>
          </div>

          <EnhancedTable
            dataSource={optimizationResults}
            columns={columns.filter(col => visibleColumns.includes(col.key))}
            exportFilename="optimization_results_export"
            exportCopyFormat={null} 
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
        key={selectedCard?.id}
        open={isModalVisible}
        onCancel={handleModalClose}
        footer={null}
        width={800}
        destroyOnClose
      >
        <Spin spinning={isModalLoading} tip="Loading card details...">
        { cardData ? (
          <ScryfallCardView
            key={`${selectedCard?.id}-${cardData.id}`}
            cardData={cardData}
            mode={modalMode}
            onSave={handleSaveEdit}
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

export default Results;