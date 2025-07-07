import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient} from '@tanstack/react-query';
import { 
  Spin, Card, Tag, Typography, Space, Button, Modal, message, Popconfirm, Input, 
  Alert, Progress, Statistic, Row, Col, Badge, Tooltip, Descriptions 
} from 'antd';

import { useLocation } from 'react-router-dom';

import { 
  CheckCircleOutlined, WarningOutlined, DeleteOutlined, SearchOutlined, ClearOutlined,
  ExperimentOutlined, ClockCircleOutlined, TrophyOutlined, BarChartOutlined,
  ThunderboltOutlined, RobotOutlined, InfoCircleOutlined, DashboardOutlined
} from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import { useSettings } from '../utils/SettingsContext';
import { useNotification } from '../utils/NotificationContext';
import { useApiWithNotifications } from '../utils/useApiWithNotifications';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import api from '../utils/api';
import ColumnSelector from '../components/ColumnSelector';
import { getColumnSearchProps, getStandardPagination } from '../utils/tableConfig';
import EnhancedTable from '../components/EnhancedTable';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';
import { useFetchScryfallCard } from '../hooks/useFetchScryfallCard';
import ScryfallCardView from '../components/Shared/ScryfallCardView';

const { Title, Text } = Typography;

// helper functions for backward compatibility
const getResultMetrics = (result) => {
  // Get best solution with fallback logic
  const bestSolution = result.solutions?.find(s => s.is_best_solution) || result.best_solution;
  
  if (!bestSolution) {
    return {
      cardsRequiredTotal: 0,
      cardsRequiredUnique: 0,
      cardsFoundTotal: 0,
      cardsFoundUnique: 0,
      completenessByQuantity: 0,
      completenessByUnique: 0,
      isComplete: false,
      missingCardsCount: 0,
      totalPrice: 0,
      numberStore: 0
    };
  }

  // Use new fields if available, fallback to legacy fields
  const cardsRequiredTotal = bestSolution.cards_required_total ?? 0;
  const cardsRequiredUnique = bestSolution.cards_required_unique ?? 
    (cardsRequiredTotal - (bestSolution.missing_cards_count ?? 0));
  const cardsFoundTotal = bestSolution.cards_found_total ?? 
    bestSolution.nbr_card_in_solution ?? bestSolution.total_card_found ?? 0;
  const cardsFoundUnique = bestSolution.cards_found_unique ?? 
    (cardsRequiredUnique - (bestSolution.missing_cards_count ?? 0));
  
  // Use new completeness fields if available, calculate if not
  const completenessByQuantity = bestSolution.completeness_by_quantity ?? 
    (cardsRequiredTotal > 0 ? cardsFoundTotal / cardsRequiredTotal : 0);
  const completenessByUnique = bestSolution.completeness_by_unique ?? 
    (cardsRequiredUnique > 0 ? cardsFoundUnique / cardsRequiredUnique : 0);
  
  const isComplete = bestSolution.is_complete ?? (bestSolution.missing_cards_count === 0);
  const missingCardsCount = bestSolution.missing_cards_count ?? 0;
  
  return {
    cardsRequiredTotal,
    cardsRequiredUnique,
    cardsFoundTotal,
    cardsFoundUnique,
    completenessByQuantity,
    completenessByUnique,
    isComplete,
    missingCardsCount,
    totalPrice: bestSolution.total_price ?? 0,
    numberStore: bestSolution.number_store ?? 0
  };
};

const Results = () => {
  const { theme } = useTheme();
  const { settings } = useSettings(); 
  const location = useLocation();
  const [selectedResult, setSelectedResult] = useState(null);
  const [selectedCard, setSelectedCard] = useState(null);
  const [modalMode, setModalMode] = useState('view');
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const queryClient = useQueryClient();
  const [cardData, setFetchedCard] = useState(null);
  const [hasShownSuccessMessage, setHasShownSuccessMessage] = useState(false);
  const [showPerformanceDetails, setShowPerformanceDetails] = useState(false);
  const { messageApi, notificationApi } = useNotification();
  const { deleteWithNotifications } = useApiWithNotifications();
  const {
    mutateAsync: fetchCard,
  } = useFetchScryfallCard();

  // table handler
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
      'id', 'created_at', 'buylist_name', 'algorithm', 'performance', 'stats', 'best_solution', 'status', 'action'
    ]
  }, 'optimization_results_table');

  // optimization results query
  const { 
    data: optimizationResults = [], 
    isLoading: loading 
  } = useQuery({
    queryKey: ['optimizations'],
    queryFn: () => api.get('/results').then(res => res.data),
    staleTime: 300000
  });

  // Performance analytics query
  const { 
    data: performanceAnalytics 
  } = useQuery({
    queryKey: ['optimization_analytics'],
    queryFn: () => api.get('/optimization_analytics').then(res => res.data),
    staleTime: 600000, // 10 minutes
    enabled: settings?.enablePerformanceMonitoring
  });

  useEffect(() => {
    if (location.state?.fromOptimization && !hasShownSuccessMessage) {
      if (!loading && optimizationResults && optimizationResults.length > 0) {
        const latestResult = optimizationResults[0];
        setSelectedResult(latestResult);
        
        // success message with algorithm info
        const algorithmUsed = latestResult.algorithm_used || 'Unknown';
        const executionTime = latestResult.execution_time || 0;
        
        notificationApi.success({
          message: 'Optimization Complete',
          description: `🎉 Optimization using ${algorithmUsed.toUpperCase()} algorithm completed in ${executionTime.toFixed(1)}s!`,
          placement: 'topRight',
        });
        setHasShownSuccessMessage(true);
        
        window.history.replaceState({}, document.title);
      }
    }
  }, [optimizationResults, location.state, loading, hasShownSuccessMessage, notificationApi]);

  // helper functions
  const getAlgorithmIcon = (algorithm) => {
    const icons = {
      'auto': <RobotOutlined />,
      'milp': <TrophyOutlined />,
      'nsga2': <ExperimentOutlined />,
      'nsga-ii-improved': <ExperimentOutlined />,
      'nsga3': <ExperimentOutlined />,
      'nsga-iii-enhanced': <ExperimentOutlined />,
      'moead': <BarChartOutlined />,
      'moea/d': <BarChartOutlined />,
      'hybrid': <ThunderboltOutlined />,
      'hybrid-milp-nsga-ii': <ThunderboltOutlined />,
      'hybrid-milp-moea/d': <ThunderboltOutlined />
    };
    return icons[algorithm?.toLowerCase()] || <ExperimentOutlined />;
  };

  const getAlgorithmColor = (algorithm) => {
    const colors = {
      'auto': 'cyan',
      'milp': 'gold',
      'nsga2': 'green',
      'nsga-ii-improved': 'green',
      'nsga3': 'blue',
      'nsga-iii-enhanced': 'blue',
      'moead': 'purple',
      'moea/d': 'purple',
      'hybrid': 'volcano',
      'hybrid-milp-nsga-ii': 'volcano',
      'hybrid-milp-moea/d': 'volcano'
    };
    return colors[algorithm?.toLowerCase()] || 'blue';
  };

  const getPerformanceScore = (result) => {
    // Use the backend calculated score if available
    if (result.performance_score) {
      return result.performance_score;
    }
    
    // Fallback to frontend calculation using new metrics
    if (!result.performance_stats && !result.execution_time) return null;
    
    const metrics = getResultMetrics(result);
    if (!metrics.cardsRequiredTotal) return null;
    
    const completeness = metrics.completenessByQuantity * 100;
    const timeScore = Math.max(0, 100 - (result.execution_time || 0) / 3);
    const qualityScore = completeness;
    
    return Math.round((timeScore + qualityScore) / 2);
  };

  const getPerformanceScoreTooltip = (result) => {
    const score = getPerformanceScore(result);
    const execTime = result.execution_time || 0;
    const metrics = getResultMetrics(result);
    
    const factors = [];
    if (metrics.completenessByQuantity < 1.0) {
      factors.push(`Solution completeness: ${(metrics.completenessByQuantity * 100).toFixed(1)}%`);
    }
    if (execTime > 60) {
      factors.push(`Execution time: ${execTime.toFixed(1)}s (longer times reduce score)`);
    }
    if (metrics.numberStore > 10) {
      factors.push(`Store count: ${metrics.numberStore} stores (more stores may impact efficiency)`);
    }
    
    let tooltip = `Performance Score: ${score}%\n\nThis score considers multiple factors:\n• Solution completeness\n• Execution time efficiency\n• Algorithm convergence\n• Resource usage`;
    
    if (factors.length > 0) {
      tooltip += `\n\nFactors affecting this score:\n• ${factors.join('\n• ')}`;
    }
    
    if (metrics.isComplete && score < 90) {
      tooltip += `\n\nNote: Even complete solutions may have lower scores due to execution time or other efficiency factors.`;
    }
    
    return tooltip;
  };

  const getAlgorithmDescription = (algorithm) => {
    const descriptions = {
      'auto': 'Automatically selects the best algorithm based on problem characteristics',
      'milp': 'Mixed Integer Linear Programming - guarantees optimal solutions for smaller problems',
      'nsga-ii-improved': 'Non-dominated Sorting Genetic Algorithm II - excellent for large multi-objective problems',
      'nsga-iii-enhanced': 'Reference point-based genetic algorithm with enhanced diversity maintenance',
      'moea/d': 'Multi-Objective Evolutionary Algorithm based on Decomposition - advanced constraint handling',
      'hybrid-milp-nsga-ii': 'Combines MILP precision with evolutionary algorithm scalability',
      'hybrid-milp-moea/d': 'Combines MILP precision with evolutionary algorithm scalability'
    };
    return descriptions[algorithm?.toLowerCase()] || 'Unknown algorithm';
  };

  // performance metrics component
  const PerformanceMetrics = ({ result }) => {
    const score = getPerformanceScore(result);
    const execTime = result.execution_time;
    const algorithm = result.algorithm_used;
    const perfStats = result.performance_stats;
    const tooltipText = getPerformanceScoreTooltip(result);

    if (!score && !execTime && !algorithm) {
      return <Text type="secondary">No performance data</Text>;
    }

    return (
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {algorithm && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            {getAlgorithmIcon(algorithm)}
            <Tag color={getAlgorithmColor(algorithm)} style={{ margin: 0 }}>
              {algorithm.toUpperCase()}
            </Tag>
          </div>
        )}
        
        {score && (
          <Tooltip title={tooltipText} overlayStyle={{ whiteSpace: 'pre-line', maxWidth: '400px' }}>
            <Progress 
              percent={score} 
              size="small" 
              status={score >= 80 ? 'success' : score >= 60 ? 'normal' : 'exception'}
              format={percent => `${percent}%`}
              style={{ cursor: 'help' }}
            />
          </Tooltip>
        )}
        
        {execTime && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <ClockCircleOutlined style={{ fontSize: '12px' }} />
            <Text style={{ fontSize: '12px' }}>{execTime.toFixed(1)}s</Text>
          </div>
        )}
        
        {perfStats?.iterations && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Text style={{ fontSize: '11px', color: '#666' }}>
              {perfStats.iterations} iterations
            </Text>
          </div>
        )}
      </Space>
    );
  };

  // Algorithm details component for expanded view
  const AlgorithmDetails = ({ result }) => {
    const algorithm = result.algorithm_used;
    const execTime = result.execution_time;
    const perfStats = result.performance_stats;

    if (!algorithm) return null;

    return (
      <Card size="small" style={{ marginBottom: '16px' }}>
        <Descriptions 
          title={
            <Space>
              {getAlgorithmIcon(algorithm)}
              <span>Algorithm Details</span>
            </Space>
          }
          size="small" 
          column={2}
        >
          <Descriptions.Item label="Algorithm">
            <Tag color={getAlgorithmColor(algorithm)}>{algorithm.toUpperCase()}</Tag>
          </Descriptions.Item>
          
          {execTime && (
            <Descriptions.Item label="Execution Time">
              <Space>
                <ClockCircleOutlined />
                {execTime.toFixed(2)} seconds
              </Space>
            </Descriptions.Item>
          )}
          
          {perfStats?.convergence_achieved && (
            <Descriptions.Item label="Convergence">
              <Tag color="green">Achieved</Tag>
            </Descriptions.Item>
          )}
          
          {perfStats?.iterations && (
            <Descriptions.Item label="Iterations">
              {perfStats.iterations}
            </Descriptions.Item>
          )}
          
          {perfStats?.memory_usage && (
            <Descriptions.Item label="Memory Usage">
              {(perfStats.memory_usage / 1024 / 1024).toFixed(1)} MB
            </Descriptions.Item>
          )}
          
          {perfStats?.solution_quality && (
            <Descriptions.Item label="Solution Quality">
              <Progress 
                percent={perfStats.solution_quality * 100} 
                size="small" 
                showInfo={false}
              />
            </Descriptions.Item>
          )}
        </Descriptions>
        
        <Alert
          message={getAlgorithmDescription(algorithm)}
          type="info"
          style={{ marginTop: '8px' }}
          showIcon
        />
      </Card>
    );
  };

  // Rest of the existing methods remain the same...
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
      notificationApi.error({
        message: 'Failed to fetch card details', 
        description: err.message || 'Failed to fetch card data',
        placement: 'topRight',
      });
      setIsModalVisible(false);
    } finally {
      setIsModalLoading(false);
    }
  };

  const handleSaveEdit = (updatedData) => {
    setIsModalVisible(false);
  };

  const formatDate = (input) => {
    if (!input) return '—';
  
    try {
      const date = new Date(input);
      if (isNaN(date)) return input;
  
      return new Intl.DateTimeFormat('en-CA', {
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(date);
    } catch (err) {
      console.error('Error formatting date:', err);
      return input;
    }
  };
  
  // Delete mutation for multiples optimization results
  const deleteBulkOptimizationMutation = useMutation({
    mutationFn: (ids) =>
      api.delete('/results/bulk-delete', {
        data: { ids: ids },
      }),
    onMutate: async (ids) => {
      await queryClient.cancelQueries(['optimizations']);
      const previousResults = queryClient.getQueryData(['optimizations']);
  
      // Optimistically remove the selected results
      queryClient.setQueryData(['optimizations'], old =>
        old ? old.filter(result => !ids.includes(result.id)) : []
      );
  
      return { previousResults };
    },
    onError: (err, ids, context) => {
      queryClient.setQueryData(['optimizations'], context.previousResults);
      notificationApi.error({
        message: 'Failed to delete selected optimizations',
        description: err.message || 'An error occurred while deleting optimizations.',
        placement: 'topRight',
      });
    },
    onSuccess: (_, ids) => {
      notificationApi.success({
        message: 'Selected optimizations deleted successfully',
        placement: 'topRight',
      });
  
      // Deselect if current result was among the deleted
      if (selectedResult && ids.includes(selectedResult.id)) {
        setSelectedResult(null);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries(['optimizations']);
      queryClient.invalidateQueries(['optimization_analytics']);
      queryClient.invalidateQueries(['results']);
    }
  });
  
  
  // Delete mutation for optimization results
  const deleteOptimizationMutation = useMutation({
    mutationFn: (resultId) => api.delete(`/results/${resultId}`),
    onMutate: async (resultId) => {
      await queryClient.cancelQueries(['optimizations']);
      const previousResults = queryClient.getQueryData(['optimizations']);
      queryClient.setQueryData(['optimizations'], old => 
        old ? old.filter(result => result.id !== resultId) : []
      );
      return { previousResults };
    },
    onError: (err, resultId, context) => {
      queryClient.setQueryData(['optimizations'], context.previousResults);
      notificationApi.error({
        message: 'Failed to delete optimization',
        description: err.message || 'Failed to delete optimization', 
        placement: 'topRight',
      });
    },
    onSuccess: (_, resultId) => {
      notificationApi.success({
        message: 'Optimization deleted successfully',
        placement: 'topRight',
      });
      if (selectedResult && selectedResult.id === resultId) {
        setSelectedResult(null);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries(['optimizations']);
      queryClient.invalidateQueries(['optimization_analytics']);
    }
  });
  
  const handleDelete = useCallback(async (resultId) => {
    await deleteWithNotifications(
      async () => {
        await deleteOptimizationMutation.mutateAsync(resultId);
        return { count: 1 };
      },
      'optimization result',
      {
        loadingMessage: 'Deleting optimization result...',
        onSuccess: () => {
          queryClient.invalidateQueries(['results']);
        },
        onError: () => {
          queryClient.invalidateQueries(['results']);
        },
      }
    );
  }, [deleteOptimizationMutation, queryClient, deleteWithNotifications]);
  

  const handleBulkDelete = useCallback(async () => {
    const idList = Array.from(selectedResultIds);
    await deleteWithNotifications(
      async () => {
        const count = idList.length;
        await deleteBulkOptimizationMutation.mutateAsync(idList);
        return { count };
      },
      'optimization results',
      {
        loadingMessage: `Deleting ${idList.length} result(s)...`,
        onSuccess: () => {
          setSelectedResultIds(new Set());
          queryClient.invalidateQueries(['results']);
        },
        onError: () => {
          queryClient.invalidateQueries(['results']);
        }
      }
    );
  }, [
    selectedResultIds,
    deleteBulkOptimizationMutation,
    setSelectedResultIds,
    queryClient,
    deleteWithNotifications,
  ]);
  
  // columns with better algorithm and performance display
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
      title: 'Algorithm & Performance',
      key: 'algorithm',
      width: 200,
      filters: [
        { text: 'Auto-Select', value: 'auto' },
        { text: 'MILP', value: 'milp' },
        { text: 'NSGA-II', value: 'nsga2' },
        { text: 'NSGA-II-Improved', value: 'nsga-ii-improved' },
        { text: 'NSGA-III', value: 'nsga3' },
        { text: 'NSGA-III-Enhanced', value: 'nsga-iii-enhanced' },
        { text: 'MOEA/D', value: 'moead' },
        { text: 'Hybrid', value: 'hybrid' },
      ],
      onFilter: (value, record) => {
        const algo = record.algorithm_used?.toLowerCase();
        return algo === value || algo?.includes(value);
      },
      filteredValue: filteredInfo.algorithm || null,
      render: (_, record) => <PerformanceMetrics result={record} />,
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
      render: (_, record) => {
        const metrics = getResultMetrics(record);
        return (
          <Space direction="vertical" size="small">
            <div>
              <Tag color="blue">{`${record.sites_scraped || 0} Sites`}</Tag>
              <Tag color="purple">{`${record.cards_scraped || 0}/${metrics.cardsRequiredTotal || 0} Cards`}</Tag>
            </div>
            {record.performance_stats?.iterations && (
              <Tag color="cyan" style={{ fontSize: '11px' }}>
                {`${record.performance_stats.iterations} Iter`}
              </Tag>
            )}
          </Space>
        );
      },
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
        const metrics = getResultMetrics(record);
        if (metrics.cardsRequiredTotal === 0) return value === 'failed';
        
        if (value === 'complete') return metrics.isComplete;
        if (value === 'partial') return !metrics.isComplete && metrics.cardsFoundTotal > 0;
        if (value === 'failed') return metrics.cardsFoundTotal === 0;
        return false;
      },
      filteredValue: filteredInfo.best_solution || null,
      render: (_, record) => {
        const metrics = getResultMetrics(record);
        
        if (metrics.cardsRequiredTotal === 0) {
          return <Tag color="red">No solution</Tag>;
        }

        const percentage = (metrics.completenessByQuantity * 100).toFixed(1);

        return (
          <Space direction="vertical" size="small">
            <div>
              <Tag color="blue">{`${metrics.numberStore} Stores`}</Tag>
              <Tag color={metrics.isComplete ? 'green' : 'orange'}>
                {metrics.isComplete ? 'Complete' : `${percentage}%`}
              </Tag>
            </div>
            <Text strong>${metrics.totalPrice.toFixed(2)}</Text>
            {/* Show metrics if available */}
            {record.best_solution?.completeness_by_unique !== undefined && (
              <Tag color="cyan" style={{ fontSize: '11px' }}>
                {`${metrics.cardsFoundUnique}/${metrics.cardsRequiredUnique} Types`}
              </Tag>
            )}
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
        const metrics = getResultMetrics(record);
        
        if (metrics.cardsRequiredTotal === 0) {
          return <Tag color="red">Failed</Tag>;
        }
        
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
          onCancel={(e) => e && e.stopPropagation()}
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <Title level={2}>
          Optimization History
          <Badge 
            count={`${optimizationResults.length} Results`} 
            style={{ backgroundColor: '#1890ff', marginLeft: '12px' }} 
          />
        </Title>
        
        {settings?.enablePerformanceMonitoring && performanceAnalytics && (
          <Button
            type="dashed"
            icon={<DashboardOutlined />}
            onClick={() => setShowPerformanceDetails(!showPerformanceDetails)}
          >
            {showPerformanceDetails ? 'Hide' : 'Show'} Analytics
          </Button>
        )}
      </div>

      {/* Performance Analytics Dashboard */}
      {showPerformanceDetails && performanceAnalytics && (
        <Card style={{ marginBottom: '24px' }}>
          <Title level={4}>Performance Analytics</Title>
          <Row gutter={16}>
            <Col span={6}>
              <Statistic
                title="Average Execution Time"
                value={performanceAnalytics.avg_execution_time || 0}
                precision={2}
                suffix="s"
                prefix={<ClockCircleOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="Success Rate"
                value={performanceAnalytics.success_rate || 0}
                precision={1}
                suffix="%"
                prefix={<CheckCircleOutlined />}
                valueStyle={{ color: (performanceAnalytics.success_rate || 0) > 90 ? '#3f8600' : '#cf1322' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="Most Used Algorithm"
                value={performanceAnalytics.most_used_algorithm || 'N/A'}
                prefix={getAlgorithmIcon(performanceAnalytics.most_used_algorithm)}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="Average Solution Quality"
                value={performanceAnalytics.avg_solution_quality || 0}
                precision={1}
                suffix="%"
                prefix={<TrophyOutlined />}
                valueStyle={{ color: (performanceAnalytics.avg_solution_quality || 0) > 80 ? '#3f8600' : '#faad14' }}
              />
            </Col>
          </Row>
          
          {performanceAnalytics?.algorithm_comparison && (
            <div style={{ marginTop: '16px' }}>
              <Text strong>Algorithm Performance Comparison:</Text>
              <div style={{ marginTop: '8px' }}>
                {Object.entries(performanceAnalytics.algorithm_comparison).map(([algorithm, stats]) => (
                  <div key={algorithm} style={{ marginBottom: '8px' }}>
                    <Space>
                      {getAlgorithmIcon(algorithm)}
                      <Text strong>{algorithm.toUpperCase()}:</Text>
                      <Tag color="blue">Avg: {stats.avg_time?.toFixed(1) || 0}s</Tag>
                      <Tag color="green">Success: {stats.success_rate?.toFixed(1) || 0}%</Tag>
                      <Tag color="purple">Used: {stats.usage_count || 0} times</Tag>
                    </Space>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {selectedResult ? (
        <>
          <Button 
            type="link" 
            onClick={() => {
              setSelectedResult(null);
              handleResetAllFilters();
            }} 
            className="mb-4"
          >
            ← Back to History
          </Button>
          
          {/* result display with algorithm information */}
          <AlgorithmDetails result={selectedResult} />
          
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

          {/* guidance for new users */}
          {optimizationResults.length === 0 && (
            <Alert
              message="No Optimization Results Yet"
              description={
                <Space direction="vertical">
                  <Text>You haven't run any optimizations yet. Get started by:</Text>
                  <ul style={{ paddingLeft: '20px', marginTop: '8px' }}>
                    <li>Going to the <strong>Optimize</strong> page</li>
                    <li>Selecting a buylist with MTG cards</li>
                    <li>Choosing your preferred sites and algorithm</li>
                    <li>Running an <strong>Optimization</strong> for best results</li>
                  </ul>
                </Space>
              }
              type="info"
              showIcon
            />
          )}

          {optimizationResults.length > 0 && (
            <>
              {/* quick stats summary with new metrics */}
              <div style={{ marginBottom: '16px' }}>
                <Row gutter={16}>
                  <Col span={6}>
                    <Card size="small">
                      <Statistic
                        title="Total Optimizations"
                        value={optimizationResults.length}
                        prefix={<ExperimentOutlined />}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small">
                      <Statistic
                        title="Most Used Algorithm"
                        value={
                          (() => {
                            const algoCounts = optimizationResults.reduce((acc, result) => {
                              const algo = result.algorithm_used || 'Unknown';
                              acc[algo] = (acc[algo] || 0) + 1;
                              return acc;
                            }, {});
                            const sorted = Object.entries(algoCounts).sort((a, b) => b[1] - a[1]);
                            return sorted.length > 0 ? `${sorted[0][0].toUpperCase()} (${sorted[0][1]})` : 'None';
                          })()
                        }
                        prefix={<ThunderboltOutlined />}
                        valueStyle={{
                          color: '#1890ff'
                        }}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small">
                      <Statistic
                        title="Complete Solutions"
                        value={optimizationResults.filter(r => {
                          const metrics = getResultMetrics(r);
                          return metrics.isComplete;
                        }).length}
                        suffix={`/ ${optimizationResults.length}`}
                        prefix={<CheckCircleOutlined />}
                        valueStyle={{ color: '#3f8600' }}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small">
                      <Statistic
                        title="Avg. Execution Time"
                        value={
                          optimizationResults
                            .filter(r => r.execution_time)
                            .reduce((sum, r) => sum + r.execution_time, 0) /
                          Math.max(optimizationResults.filter(r => r.execution_time).length, 1)
                        }
                        precision={1}
                        suffix="s"
                        prefix={<ClockCircleOutlined />}
                      />
                    </Card>
                  </Col>
                </Row>
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
                scroll={{ x: 1400 }} // Increased for more columns
              />
            </>
          )}
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
          {cardData ? (
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