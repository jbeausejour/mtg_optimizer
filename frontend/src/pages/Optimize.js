import React, { useState, useEffect, useRef } from 'react';
import api from '../utils/api';
import { useNotification } from '../utils/NotificationContext';
import { useApiWithNotifications } from '../utils/useApiWithNotifications';
import { 
  TrophyOutlined, 
  ShopOutlined, 
  DollarOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined,
  EyeOutlined,
  ExperimentOutlined
} from '@ant-design/icons';
import {
  Alert, 
  Button, 
  message, 
  Row, 
  Col, 
  Card, 
  List, 
  Modal, 
  Switch, 
  InputNumber, 
  Select, 
  Typography, 
  Spin, 
  Divider, 
  Space,
  Tag, 
  Tooltip, 
  Collapse,
  Badge
} from 'antd';
import { useTheme } from '../utils/ThemeContext';
import NormalizedWeightSliders, { weightConfig } from '../components/NormalizedWeightSliders';

import BeautifulProgressDisplay from '../components/BeautifulProgressDisplay';
import { useNavigate } from 'react-router-dom';

import RadarChart from '../components/RadarChart';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import SubtaskProgress from '../components/SubtaskProgress';
import { useBuylistState } from '../hooks/useBuylistState';
import { useFetchScryfallCard } from '../hooks/useFetchScryfallCard';
import ScryfallCardView from '../components/Shared/ScryfallCardView';

const { Title, Text } = Typography;
const { Panel } = Collapse;
const { Option, OptGroup } = Select;

const Optimize = () => {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const { Option } = Select;

  // Notification hooks
  const { messageApi, notificationApi } = useNotification();
  const { executeWithNotifications, fetchWithNotifications } = useApiWithNotifications();

  const [cards, setCards] = useState([]);
  const [selectedCard, setSelectedCard] = useState({});

  const [sites, setSites] = useState([]);
  const [siteType, setSiteType] = useState('extended');
  const [selectedSites, setSelectedSites] = useState({});

  // optimization strategy state
  const [optimizationStrategy, setOptimizationStrategy] = useState('auto');
  const [fallbackStrategy, setFallbackStrategy] = useState('milp');
  
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isOptimizationComplete, setIsOptimizationComplete] = useState(false);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const [minStore, setMinStore] = useState(3);
  const [maxStore, setMaxStore] = useState(15);
  const [previousMinStore, setPreviousMinStore] = useState(3);
  const [previousMaxStore, setPreviousMaxStore] = useState(15);
  const [findMinStore, setFindMinStore] = useState(true);
  
  const taskRef = useRef(null);
  const [taskId, setTaskId] = useState(null);
  const [taskState, setTaskState] = useState(null);
  const [taskDetails, setTaskDetails] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [taskProgress, setTaskProgress] = useState(0);
  const [subtasks, setSubtasks] = useState(null);

  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [modalMode, setModalMode] = useState('view');

  const [countryFilter, setCountryFilter] = useState('canada'); 
  const [methodFilter, setMethodFilter] = useState(['all']); 

  const [presetMode, setPresetMode] = useState("custom");

  const [selectedSiteCount, setSelectedSiteCount] = useState(0); 
  const [buylists, setBuylists] = useState([]); 
  const { selectedBuylist, setSelectedBuylist} = useBuylistState();
  const [minAge, setMinAge] = useState(3600);  // default 1 hour
  const [strictPreferences, setStrictPreferences] = useState(false);
  
  // algorithm configuration with NSGA-III support
  const [algorithmConfig, setAlgorithmConfig] = useState({
    time_limit: 300,
    max_iterations: 1000,
    early_stopping: true,
    convergence_threshold: 0.001,
    population_size: 200,
    neighborhood_size: 20,
    decomposition_method: 'tchebycheff',
    milp_gap_tolerance: 0.01,
    hybrid_milp_time_fraction: 0.3,
    reference_point_divisions: 12  // NSGA-III specific parameter
  });

  const defaultWeights = { cost: 1.0, quality: 1.0, store_count: 0.3 };
  const [weights, setWeights] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('mtg_weights'));
      if (saved && typeof saved === 'object') {
        const sanitized = Object.fromEntries(
          Object.entries(saved).map(([k, v]) => [k, Math.max(v, 0.0001)])
        );
        return sanitized;
      }
    } catch {}
    return defaultWeights;
  });

  const [cardData, setFetchedCard] = useState(null);
  const {
    mutateAsync: fetchCard,
  } = useFetchScryfallCard();

  // Enhanced presets with algorithm-specific configurations including all algorithms
  const presets = {
    // MILP Presets
    cheapest: {
      cost: 10.0,
      quality: 0.1,
      store_count: 0.1,
      algorithm: 'milp',
      description: 'Find absolute lowest cost using precise MILP optimization'
    },
    optimal_small: {
      cost: 5.0,
      quality: 3.0,
      store_count: 2.0,
      algorithm: 'milp',
      description: 'Guaranteed optimal solution for small problems (≤50 cards)'
    },
    
    // NSGA-II Presets
    large_balanced: {
      cost: 3.0,
      quality: 3.0,
      store_count: 1.0,
      algorithm: 'nsga2',
      description: 'Balanced multi-objective optimization for large problems'
    },
    quality_diversity: {
      cost: 1.0,
      quality: 5.0,
      store_count: 2.0,
      algorithm: 'nsga2',
      description: 'High quality cards with good solution diversity using NSGA-II'
    },
    
    // NSGA-III Presets
    best_quality: {
      cost: 0.1,
      quality: 10.0,
      store_count: 0.1,
      algorithm: 'nsga3',
      description: 'Maximum quality focus with systematic diversity via reference points'
    },
    maximum_diversity: {
      cost: 1.0,
      quality: 3.0,
      store_count: 1.0,
      algorithm: 'nsga3',
      description: 'Systematic solution diversity using NSGA-III reference points'
    },
    very_large_problems: {
      cost: 2.0,
      quality: 4.0,
      store_count: 1.5,
      algorithm: 'nsga3',
      description: 'Optimized for very large problems (>100 cards) with enhanced diversity'
    },
    
    // MOEA/D Presets
    constrained_optimization: {
      cost: 4.0,
      quality: 4.0,
      store_count: 3.0,
      algorithm: 'moead',
      description: 'Decomposition-based approach for complex constrained problems'
    },
    convergence_focused: {
      cost: 3.0,
      quality: 5.0,
      store_count: 2.0,
      algorithm: 'moead',
      description: 'Superior convergence for multi-objective problems using MOEA/D'
    },
    
    // Hybrid MILP+MOEA/D Presets
    fewest_stores: {
      cost: 1.0,
      quality: 1.0,
      store_count: 5.0,
      algorithm: 'hybrid',
      description: 'Minimize stores using hybrid MILP+MOEA/D approach'
    },
    robust_medium: {
      cost: 3.0,
      quality: 3.0,
      store_count: 2.0,
      algorithm: 'hybrid',
      description: 'Robust performance for medium problems (20-100 cards)'
    },
    
    // Hybrid MILP+NSGA-III Presets
    premium_complex: {
      cost: 1.0,
      quality: 8.0,
      store_count: 1.0,
      algorithm: 'hybrid_milp_nsga3',
      description: 'Premium quality with maximum diversity for complex scenarios'
    },
    enterprise_scale: {
      cost: 2.0,
      quality: 4.0,
      store_count: 3.0,
      algorithm: 'hybrid_milp_nsga3',
      description: 'Enterprise-scale optimization combining MILP precision with NSGA-III diversity'
    },
    
    // Auto-Select Presets
    balanced: {
      cost: 3.0,
      quality: 3.0,
      store_count: 1.0,
      algorithm: 'auto',
      description: 'Let the system choose the best algorithm automatically'
    },
    smart_adaptive: {
      cost: 2.0,
      quality: 4.0,
      store_count: 2.0,
      algorithm: 'auto',
      description: 'Adaptive algorithm selection based on problem characteristics'
    }
  };

  // Algorithm metadata for user guidance with complete information
  const algorithmInfo = {
    auto: {
      name: 'Auto-Select',
      description: 'Automatically chooses the best algorithm based on problem size and characteristics',
      icon: '🤖',
      bestFor: 'General use - let the system decide based on problem complexity',
      pros: ['Optimal algorithm selection', 'No configuration needed', 'Adapts to problem size'],
      cons: ['Less control over specific behavior', 'May not use preferred algorithm']
    },
    milp: {
      name: 'MILP',
      description: 'Mixed Integer Linear Programming - finds mathematically optimal solutions',
      icon: '🎯',
      bestFor: 'Small to medium problems (≤50 cards, ≤20 stores) requiring guaranteed optimality',
      pros: ['Guaranteed optimal solution', 'Fast for small problems', 'Precise mathematical approach'],
      cons: ['Memory intensive for large problems', 'May timeout on complex instances', 'Not scalable']
    },
    nsga2: {
      name: 'NSGA-II',
      description: 'Non-dominated Sorting Genetic Algorithm II - proven multi-objective optimization',
      icon: '🧬',
      bestFor: 'Large problems (50-100 cards) with multiple competing objectives',
      pros: ['Scalable to large problems', 'Good solution diversity', 'Handles constraints well', 'Well-established'],
      cons: ['No optimality guarantee', 'Requires parameter tuning', 'Can struggle with many objectives']
    },
    nsga3: {
      name: 'NSGA-III',
      description: 'Reference point-based genetic algorithm with systematic diversity maintenance',
      icon: '🔬',
      bestFor: 'Very large problems (>100 cards) requiring systematic solution diversity',
      pros: ['Superior diversity maintenance', 'Reference point guidance', 'Better convergence for many objectives', 'Systematic exploration'],
      cons: ['More complex than NSGA-II', 'Requires larger populations', 'Longer execution time', 'Parameter sensitive']
    },
    moead: {
      name: 'MOEA/D',
      description: 'Multi-Objective Evolutionary Algorithm based on Decomposition',
      icon: '🔬',
      bestFor: 'Complex multi-objective problems with tight constraints and convergence requirements',
      pros: ['Excellent convergence properties', 'Good for constrained problems', 'Efficient resource utilization', 'Robust performance'],
      cons: ['Slower than NSGA-II', 'Complex parameter configuration', 'Less diversity than NSGA-III']
    },
    hybrid: {
      name: 'Hybrid MILP+MOEA/D',
      description: 'Combines MILP precision with evolutionary algorithm scalability',
      icon: '⚡',
      bestFor: 'Medium to large problems (20-100 cards) needing balance of quality and performance',
      pros: ['Robust performance across problem sizes', 'Good quality solutions', 'Combines best of both worlds', 'Adaptive approach'],
      cons: ['Longer execution time', 'More complex parameter tuning', 'Resource intensive']
    },
    hybrid_milp_nsga3: {
      name: 'Hybrid MILP+NSGA-III',
      description: 'Advanced hybrid combining MILP optimization with NSGA-III diversity for complex problems',
      icon: '🚀',
      bestFor: 'Very large, complex problems (>75 cards) requiring both optimality and systematic diversity',
      pros: ['MILP precision for subproblems', 'Enhanced diversity via reference points', 'Excellent for complex scenarios', 'State-of-the-art approach'],
      cons: ['Longest execution time', 'Most complex configuration', 'Very resource intensive', 'Requires expert tuning']
    }
  };
  const [isCollapsed, setIsCollapsed] = useState(false);
  
  const cancelTask = async (taskId) => {
    try {
      const response = await api.post(`cancel_task/${taskId}`);
      message.success("Task canceled.", response);
    } catch (err) {
      console.error("Failed to cancel task:", err);
      message.error("Cancel failed.");
    }
  };

  const handlePresetChange = (presetKey) => {
    const preset = presets[presetKey];
    if (preset) {
      setWeights({
        cost: preset.cost,
        quality: preset.quality,
        store_count: preset.store_count
      });
      
      // Set recommended algorithm for this preset
      if (preset.algorithm && preset.algorithm !== 'auto') {
        setOptimizationStrategy(preset.algorithm);
      }
      
      setPresetMode(presetKey);
      
      messageApi.info(`Applied ${presetKey.replace('_', ' ')} preset - ${preset.description}`);
    }
  };

  useEffect(() => {
    const allMaxed = Object.entries(weights).every(([key, val]) => {
      return val >= key;
    });
  
    if (allMaxed && !window.__allWeightsWarned) {
      messageApi.warning('All weights are maxed — this may lead to conflicting optimization goals.');
      window.__allWeightsWarned = true;
    } else if (!allMaxed) {
      window.__allWeightsWarned = false;
    }
  
    const current = localStorage.getItem('mtg_weights');
    const next = JSON.stringify(weights);
    if (current !== next) {
      localStorage.setItem('mtg_weights', next);
    }
  }, [weights, messageApi]);

  // optimization configuration with NSGA-III support
  const getOptimizationConfig = () => {
    const problemSize = {
      num_cards: cards.length,
      num_stores: selectedSiteCount,
      complexity_score: (cards.length * selectedSiteCount) / 1000
    };

    return {
      primary_algorithm: optimizationStrategy,
      weights: weights,
      min_store: findMinStore ? 1 : minStore,
      max_store: findMinStore ? 50 : maxStore,
      find_min_store: findMinStore,
      strict_preferences: strictPreferences,
      time_limit: algorithmConfig.time_limit,
      max_iterations: algorithmConfig.max_iterations,
      early_stopping: algorithmConfig.early_stopping,
      convergence_threshold: algorithmConfig.convergence_threshold,
      
      // Algorithm-specific parameters
      population_size: algorithmConfig.population_size,
      neighborhood_size: algorithmConfig.neighborhood_size,
      decomposition_method: algorithmConfig.decomposition_method,
      milp_gap_tolerance: algorithmConfig.milp_gap_tolerance,
      hybrid_milp_time_fraction: algorithmConfig.hybrid_milp_time_fraction,
      reference_point_divisions: algorithmConfig.reference_point_divisions, // NSGA-III specific
      
      // Problem characteristics for algorithm selection
      problem_characteristics: problemSize,
      
    };
  };

  const filteredSites = sites.filter(site => {
    if (!site.active) return false;
    if (countryFilter !== 'all' && site.country?.toLowerCase() !== countryFilter) {
      return false;
    }
    if (siteType === 'primary' && site.type?.toLowerCase() !== 'primary') {
      return false;
    }
    if (!methodFilter.includes('all') && !methodFilter.includes(site.method?.toLowerCase())) {
      return false;
    }
    return true;
  });

  useEffect(() => {
    const savedTaskId = localStorage.getItem('mtg_task_id');
    if (savedTaskId) {
      setTaskId(savedTaskId);
      setIsOptimizing(true);
      checkTaskStatus(savedTaskId); 
    }
    fetchSites();
    fetchBuylists();
  }, []);

  useEffect(() => {
    if (taskId) {
      taskRef.current = taskId;
      setIsOptimizing(true);
      const interval = setInterval(() => {
        checkTaskStatus(taskRef.current);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [taskId]);

  useEffect(() => {
    if (buylists.length > 0 && !selectedBuylist) {
      const first = buylists[0];
      setSelectedBuylist({ buylistId: first.id, name: first.name }); 
    }
  }, [buylists]);
  
  useEffect(() => {
    if (selectedBuylist) {
      setCards([]);
      handleSelectBuylist(selectedBuylist.buylistId);
    }
  }, [selectedBuylist]);

  useEffect(() => {
    setSelectedSiteCount(filteredSites.filter(site => selectedSites[site.id]).length);
  }, [filteredSites, selectedSites]);

  const checkTaskStatus = async (id) => {
    try {
      const response = await api.get(`/task_status/${id}`);
      setTaskState(response.data.state);
      setTaskStatus(response.data.status);
      setTaskProgress(response.data.progress ?? 0);
      setTaskDetails(response.data.details ?? null);

      // Extract subtasks and details
      if (response.data.current) {
        if (response.data.current.subtasks) {
          setSubtasks(response.data.current.subtasks);
        }
        
        // Show algorithm information if available
        if (response.data.current.algorithm_used) {
          setTaskDetails(prev => ({
            ...prev,
            algorithm_used: response.data.current.algorithm_used,
          }));
        }
      }
      
      if (response.data.state === 'SUCCESS' || response.data.state === 'FAILURE') {
        setIsOptimizing(false);
        setSubtasks(null);
        localStorage.removeItem('mtg_task_id');
        
        if (response.data.state === 'SUCCESS') {
          const optimizationData = response.data.result;
          
          // Show success notification
          notificationApi.success({
            message: 'Optimization completed successfully',
            description: `Algorithm used: ${optimizationData.algorithm_used || 'Unknown'}`,
            placement: 'topRight',
          });
          
          console.log('Setting optimization result:', optimizationData);
          
          if (optimizationData && optimizationData.solutions) {
            const bestSolution = optimizationData.solutions.find(s => s.is_best_solution);
            optimizationData.best_solution = bestSolution;
          }
          
          setOptimizationResult(optimizationData);
          setIsOptimizationComplete(true);
          
          setTimeout(() => {
            setTaskId(null);
            setIsOptimizationComplete(false);
          }, 10000);
        } else {
          notificationApi.error({
            message: 'Optimization failed',
            description: response.data.error || 'Unknown error occurred',
            placement: 'topRight',
          });
          setTaskId(null);
          setIsOptimizationComplete(false);
        }
      }
    } catch (error) {
      console.error('Error checking task status:', error);
      setIsOptimizing(false);
      setTaskId(null);
      setSubtasks(null);
      setIsOptimizationComplete(false);
    }
  };

  const handleViewResults = () => {
    if (optimizationResult) {
      const resultsElement = document.getElementById('optimization-results');
      if (resultsElement) {
        resultsElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      navigate('/results');
    }
  };

  const handleGoToResultsPage = () => {
    navigate('/results', { 
      state: { 
        fromOptimization: true,
        optimizationId: optimizationResult?.id
      } 
    });
  };

  const fetchSites = async () => {
    await fetchWithNotifications(
      async () => {
        const response = await api.get('/sites');
        const sitesWithTypes = response.data.map(site => ({
          ...site,
          type: site.type || 'primary'
        }));
        setSites(sitesWithTypes);
        const initialSelected = sitesWithTypes.reduce((acc, site) => ({
          ...acc,
          [site.id]: site.active
        }), {});
        setSelectedSites(initialSelected);
        return sitesWithTypes;
      },
      {
        operation: 'fetch',
        item: 'sites',
        showSuccessNotification: false,
      }
    );
  };

  const fetchBuylists = async () => {
    await fetchWithNotifications(
      async () => {
        const response = await api.get('/buylists');
        setBuylists(response.data);
        return response.data;
      },
      {
        operation: 'fetch',
        item: 'buylists',
        showSuccessNotification: false,
      }
    );
  };

  const handleOptimize = async () => {
    setOptimizationResult(null);
    setIsOptimizationComplete(false);
    
    await executeWithNotifications(
      async () => {
        const sitesToOptimize = filteredSites
          .filter(site => selectedSites[site.id])
          .map(site => site.id.toString());

        if (sitesToOptimize.length === 0) {
          throw new Error('Please select at least one site to optimize');
        }

        if (cards.length === 0) {
          throw new Error('Please select a buylist with cards to optimize');
        }

        const config = getOptimizationConfig();

        const response = await api.post('/start_scraping', {
          sites: sitesToOptimize,
          strategy: config.primary_algorithm,
          min_store: config.min_store,
          max_store: config.max_store,
          find_min_store: config.find_min_store,
          min_age_seconds: minAge,
          buylist_id: selectedBuylist?.buylistId,
          strict_preferences: config.strict_preferences,
          user_preferences: Object.fromEntries(
            cards.map(card => [
              card.name,
              {
                set_name: card.set_name,
                language: card.language,
                quality: card.quality,
                version: card.version
              }
            ])
          ),
          card_list: cards.map(card => ({
            name: card.name,
            set_name: card.set_name,
            language: card.language,
            quality: card.quality,
            quantity: card.quantity
          })),
          weights: config.weights,
          
          // configuration with NSGA-III support
          optimization_config: config,
          algorithm_config: algorithmConfig
        });

        setTaskId(response.data.task_id);
        setIsOptimizing(true);
        setSubtasks(null);
        localStorage.setItem('mtg_task_id', response.data.task_id);
        
        return { 
          taskId: response.data.task_id, 
          siteCount: sitesToOptimize.length,
          algorithm: config.primary_algorithm,
        };
      },
      {
        operation: 'start',
        item: 'optimization',
        loadingMessage: 'Starting optimization...',
        onSuccess: (result) => {
          messageApi.info(
            `optimization started with ${result.siteCount} sites using ${result.algorithm.toUpperCase()} algorithm!`
          );
        }
      }
    );
  };

  const handleSelectBuylist = async (buylistId) => {
    await fetchWithNotifications(
      async () => {
        const response = await api.get(`/buylists/${buylistId}`);
        setCards(response.data);
        return response.data;
      },
      {
        operation: 'load',
        item: 'buylist',
        showSuccessNotification: true,
        successMessage: 'Buylist loaded successfully'
      }
    );
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
        version: card.version || 'Standard'
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

  const handleSiteSelect = (siteId) => {
    setSelectedSites(prev => {
      const newSelectedSites = {
        ...prev,
        [siteId]: !prev[siteId]
      };
      setSelectedSiteCount(filteredSites.filter(site => newSelectedSites[site.id]).length);
      return newSelectedSites;
    });
  };

  const getCountryCounts = () => {
    const counts = sites.reduce((acc, site) => {
      if (site.active) {
        const country = site.country?.toLowerCase() || 'unknown';
        acc[country] = (acc[country] || 0) + 1;
      }
      return acc;
    }, {});
    return counts;
  };

  const getMethodCounts = () => {
    const counts = sites.reduce((acc, site) => {
      if (site.active) {
        const method = site.method?.toLowerCase() || 'unknown';
        acc[method] = (acc[method] || 0) + 1;
      }
      return acc;
    }, {});
    return counts;
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
    setFetchedCard(null);
  };

  const handleSelectAll = () => {
    const newSelectedSites = {};
    filteredSites.forEach(site => {
      newSelectedSites[site.id] = true;
    });
    setSelectedSites(prev => ({
      ...prev,
      ...newSelectedSites
    }));
  };

  const handleSelectNone = () => {
    const newSelectedSites = {};
    filteredSites.forEach(site => {
      newSelectedSites[site.id] = false;
    });
    setSelectedSites(prev => ({
      ...prev,
      ...newSelectedSites
    }));
  };

  // Calculate problem size indicators with NSGA-III consideration
  const problemSize = cards.length * selectedSiteCount;
  const problemComplexity = problemSize > 1000 ? 'High' : problemSize > 200 ? 'Medium' : 'Low';
  
  // Enhanced recommendation logic with NSGA-III
  const getRecommendedAlgorithm = () => {
    if (problemSize > 1500) return 'hybrid_milp_nsga3';  // Very large/complex problems
    if (problemSize > 1000) return 'nsga3';              // Large problems requiring diversity
    if (problemSize > 500) return 'nsga2';               // Large problems
    if (problemSize > 100) return 'hybrid';              // Medium-large problems
    return 'milp';                                       // Small problems
  };
  
  const recommendedAlgorithm = getRecommendedAlgorithm();

  // Group presets by algorithm for better organization
  const presetsByAlgorithm = Object.entries(presets).reduce((acc, [key, preset]) => {
    const algo = preset.algorithm;
    if (!acc[algo]) acc[algo] = [];
    acc[algo].push({ key, ...preset });
    return acc;
  }, {});

  return (
    <div className={`optimize section ${theme}`}>
      <Title level={2}>
        Optimization 
      </Title>
        <Collapse
          defaultActiveKey={['1']}
            activeKey={isCollapsed ? [] : ['1']}
            onChange={(keys) => setIsCollapsed(keys.length === 0)}
          >
          <Panel
            key="1"
            header={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <span><strong>Optimization Configuration & Controls</strong></span>
                {isCollapsed && (
                  <Button
                    type="primary"
                    size="large"
                    onClick={handleOptimize}
                    disabled={isOptimizing || !!taskId}
                  >
                  {isOptimizing ? 'Optimization in Progress...' : 'Run Optimization'}
                  </Button>
                )}
              </div>
            }
          >

            <Row gutter={[16, 8]} className="mb-4">
                <Col span={6}>
                  <Card size="small" title="Algorithm Selection">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      
                      <Select 
                        value={optimizationStrategy} 
                        onChange={setOptimizationStrategy} 
                        style={{ width: '100%' }}
                      >
                        {Object.entries(algorithmInfo).map(([key, info]) => (
                          <Option key={key} value={key}>
                            <Space>
                              <span>{info.icon}</span>
                              <span>{info.name}</span>
                              {key === recommendedAlgorithm && (
                                <Tag size="small" color="green">Recommended</Tag>
                              )}
                            </Space>
                          </Option>
                        ))}
                      </Select>
                      
                      {algorithmInfo[optimizationStrategy] && (
                        <Card size="small" style={{ backgroundColor: '#f6ffed' }}>
                          <Text style={{ fontSize: '12px' }}>
                            {algorithmInfo[optimizationStrategy].description}
                          </Text>
                          <br />
                          <Text type="secondary" style={{ fontSize: '11px' }}>
                            Best for: {algorithmInfo[optimizationStrategy].bestFor}
                          </Text>
                        </Card>
                      )}
                    </Space>
                  </Card>
                  

                  
                  {taskId && (
                    <Button 
                      danger 
                      onClick={() => cancelTask(taskId)}
                      style={{ width: '100%' }}
                    >
                      Cancel Task
                    </Button>
                  )}
                  
                  {/* Problem size indicator with enhanced complexity assessment */}
                  <Card size="small" title="Problem Analysis">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <div>
                        <Text strong>Problem Size: </Text>
                        <Tag color={problemComplexity === 'High' ? 'red' : problemComplexity === 'Medium' ? 'orange' : 'green'}>
                          {problemComplexity}
                        </Tag>
                        <Text type="secondary"> ({cards.length} cards × {selectedSiteCount} sites)</Text>
                      </div>
                      <div>
                        <Text strong>Recommended: </Text>
                        <Tag color="blue">{algorithmInfo[recommendedAlgorithm]?.name}</Tag>
                      </div>
                      {problemSize > 1000 && (
                        <Alert
                          message="Large Problem Detected"
                          description="Consider using NSGA-III or Hybrid MILP+NSGA-III for better diversity and performance."
                          type="info"
                          showIcon
                          style={{ fontSize: '11px' }}
                        />
                      )}
                    </Space>
                  </Card>
                  
                  {!isCollapsed && (
                    <Button 
                      type="primary" 
                      onClick={handleOptimize} 
                      className={`optimize-button ${theme}`}
                      disabled={isOptimizing || !!taskId}
                      size="large"
                      style={{ width: '100%' }}
                    >
                      {isOptimizing ? 'Optimization in Progress...' : 'Run Optimization'}
                    </Button>
                  )}
                </Col>
                
                <Col span={18}>
                  <Collapse defaultActiveKey={['1']}>
                    <Panel header={<strong>Optimization Configuration</strong>} key="1">
                      <Row gutter={16}>
                        <Col span={12}>
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <Card size="small" title="Optimization Presets">
                              <Select
                                value={presetMode}
                                onChange={handlePresetChange}
                                style={{ width: '100%' }}
                                optionLabelProp="label"
                              >
                                <Option value="custom" label="🎛 Custom Configuration">
                                  🎛 Custom Configuration
                                </Option>
                                
                                {/* Group presets by algorithm */}
                                {Object.entries(presetsByAlgorithm).map(([algorithm, presetList]) => (
                                  <Select.OptGroup key={algorithm} label={`${algorithmInfo[algorithm]?.icon || '⚙️'} ${algorithmInfo[algorithm]?.name || algorithm.toUpperCase()} Presets`}>
                                    {presetList.map(preset => (
                                      <Option 
                                        key={preset.key} 
                                        value={preset.key}
                                        label={`${algorithmInfo[algorithm]?.icon || '⚙️'} ${preset.key.charAt(0).toUpperCase() + preset.key.slice(1).replace('_', ' ')}`}
                                      >
                                        <Space>
                                          <span>{algorithmInfo[algorithm]?.icon || '⚙️'}</span>
                                          <span>{preset.key.charAt(0).toUpperCase() + preset.key.slice(1).replace('_', ' ')}</span>
                                          <Text type="secondary" style={{ fontSize: '11px' }}>
                                            ({algorithm.toUpperCase()})
                                          </Text>
                                        </Space>
                                      </Option>
                                    ))}
                                  </Select.OptGroup>
                                ))}
                              </Select>
                              
                              {presetMode !== 'custom' && presets[presetMode] && (
                                <Alert
                                  message={presets[presetMode].description}
                                  type="info"
                                  showIcon
                                  style={{ marginTop: '8px', fontSize: '12px' }}
                                />
                              )}
                            </Card>

                            {presetMode === 'custom' ? (
                              <NormalizedWeightSliders
                                onChange={(newOrUpdater) => {
                                  const nextWeights = typeof newOrUpdater === 'function'
                                    ? newOrUpdater(weights)
                                    : newOrUpdater;
                              
                                  if (JSON.stringify(weights) !== JSON.stringify(nextWeights)) {
                                    setWeights(nextWeights);
                                  }
                                }}
                                findMinStore={findMinStore}
                              />
                            ) : (
                              <Card size="small" title="Current Preset Values">
                                <Space direction="vertical" style={{ width: '100%' }}>
                                  <div><Text strong>Cost:</Text> {presets[presetMode]?.cost ?? 0}</div>
                                  <div><Text strong>Quality:</Text> {presets[presetMode]?.quality ?? 0}</div>
                                  <div><Text strong>Store Count:</Text> {presets[presetMode]?.store_count ?? 0}</div>
                                  <div><Text strong>Algorithm:</Text> 
                                    <Tag color="blue">{presets[presetMode]?.algorithm?.toUpperCase()}</Tag>
                                  </div>
                                </Space>
                              </Card>
                            )}

                            <Collapse 
                              size="small"
                              items={[
                                {
                                  key: 'advanced',
                                  label: 'Advanced Algorithm Settings',
                                  children: (
                                    <Space direction="vertical" style={{ width: '100%' }}>
                                      <Row gutter={8}>
                                        <Col span={12}>
                                          <Text strong>Time Limit (seconds)</Text>
                                          <InputNumber
                                            min={60}
                                            max={3600}
                                            value={algorithmConfig.time_limit}
                                            onChange={(value) => setAlgorithmConfig(prev => ({
                                              ...prev,
                                              time_limit: value
                                            }))}
                                            style={{ width: '100%' }}
                                          />
                                        </Col>
                                        <Col span={12}>
                                          <Text strong>Max Iterations</Text>
                                          <InputNumber
                                            min={100}
                                            max={5000}
                                            value={algorithmConfig.max_iterations}
                                            onChange={(value) => setAlgorithmConfig(prev => ({
                                              ...prev,
                                              max_iterations: value
                                            }))}
                                            style={{ width: '100%' }}
                                          />
                                        </Col>
                                      </Row>
                                      
                                      {(optimizationStrategy === 'nsga2' || optimizationStrategy === 'nsga3' || optimizationStrategy === 'moead' || optimizationStrategy === 'hybrid' || optimizationStrategy === 'hybrid_milp_nsga3') && (
                                        <Row gutter={8}>
                                          <Col span={12}>
                                            <Text strong>Population Size</Text>
                                            <InputNumber
                                              min={50}
                                              max={1000}
                                              value={algorithmConfig.population_size}
                                              onChange={(value) => setAlgorithmConfig(prev => ({
                                                ...prev,
                                                population_size: value
                                              }))}
                                              style={{ width: '100%' }}
                                            />
                                          </Col>
                                          <Col span={12}>
                                            <Text strong>Convergence Threshold</Text>
                                            <InputNumber
                                              min={0.0001}
                                              max={0.1}
                                              step={0.001}
                                              value={algorithmConfig.convergence_threshold}
                                              onChange={(value) => setAlgorithmConfig(prev => ({
                                                ...prev,
                                                convergence_threshold: value
                                              }))}
                                              style={{ width: '100%' }}
                                            />
                                          </Col>
                                        </Row>
                                      )}
                                      
                                      {/* NSGA-III specific parameters */}
                                      {(optimizationStrategy === 'nsga3' || optimizationStrategy === 'hybrid_milp_nsga3') && (
                                        <Row gutter={8}>
                                          <Col span={12}>
                                            <Text strong>Reference Point Divisions</Text>
                                            <Tooltip title="Number of divisions for reference points. Higher values provide more diversity but require larger populations.">
                                              <InputNumber
                                                min={6}
                                                max={20}
                                                value={algorithmConfig.reference_point_divisions}
                                                onChange={(value) => setAlgorithmConfig(prev => ({
                                                  ...prev,
                                                  reference_point_divisions: value
                                                }))}
                                                style={{ width: '100%' }}
                                              />
                                            </Tooltip>
                                          </Col>
                                          <Col span={12}>
                                            <Alert
                                              message="NSGA-III uses reference points for systematic diversity"
                                              type="info"
                                              style={{ fontSize: '11px' }}
                                            />
                                          </Col>
                                        </Row>
                                      )}
                                      
                                      {optimizationStrategy === 'moead' && (
                                        <Row gutter={8}>
                                          <Col span={12}>
                                            <Text strong>Neighborhood Size</Text>
                                            <InputNumber
                                              min={10}
                                              max={50}
                                              value={algorithmConfig.neighborhood_size}
                                              onChange={(value) => setAlgorithmConfig(prev => ({
                                                ...prev,
                                                neighborhood_size: value
                                              }))}
                                              style={{ width: '100%' }}
                                            />
                                          </Col>
                                          <Col span={12}>
                                            <Text strong>Decomposition Method</Text>
                                            <Select
                                              value={algorithmConfig.decomposition_method}
                                              onChange={(value) => setAlgorithmConfig(prev => ({
                                                ...prev,
                                                decomposition_method: value
                                              }))}
                                              style={{ width: '100%' }}
                                            >
                                              <Option value="tchebycheff">Tchebycheff</Option>
                                              <Option value="weighted_sum">Weighted Sum</Option>
                                              <Option value="pbi">PBI</Option>
                                            </Select>
                                          </Col>
                                        </Row>
                                      )}
                                      
                                      {/* Hybrid algorithm time allocation */}
                                      {(optimizationStrategy === 'hybrid' || optimizationStrategy === 'hybrid_milp_nsga3') && (
                                        <Row gutter={8}>
                                          <Col span={12}>
                                            <Text strong>MILP Time Fraction</Text>
                                            <Tooltip title="Fraction of total time allocated to MILP phase (0.1 = 10%, 0.3 = 30%)">
                                              <InputNumber
                                                min={0.1}
                                                max={0.5}
                                                step={0.05}
                                                value={algorithmConfig.hybrid_milp_time_fraction}
                                                onChange={(value) => setAlgorithmConfig(prev => ({
                                                  ...prev,
                                                  hybrid_milp_time_fraction: value
                                                }))}
                                                style={{ width: '100%' }}
                                              />
                                            </Tooltip>
                                          </Col>
                                          <Col span={12}>
                                            <Alert
                                              message={`${algorithmInfo[optimizationStrategy]?.name} combines MILP precision with evolutionary diversity`}
                                              type="info"
                                              style={{ fontSize: '11px' }}
                                            />
                                          </Col>
                                        </Row>
                                      )}
                                      
                                      <Switch
                                        checked={algorithmConfig.early_stopping}
                                        onChange={(checked) => setAlgorithmConfig(prev => ({
                                          ...prev,
                                          early_stopping: checked
                                        }))}
                                        checkedChildren="Early Stopping ON"
                                        unCheckedChildren="Early Stopping OFF"
                                      />
                                    </Space>
                                  )
                                }
                              ]}
                            />
                            

                            <Row gutter={12}>
                              <Col span={12}>
                                <Card size="small" title="Store Strategy">
                                  <Space direction="vertical" style={{ width: '100%' }}>
                                    <Tooltip title="Try to find the smallest number of stores that can fulfill your buylist. May take longer.">
                                      <Switch
                                        checked={findMinStore}
                                        onChange={(checked) => {
                                          setFindMinStore(checked);
                                          if (!checked && previousMinStore > 0) {
                                            setMinStore(previousMinStore);
                                          }
                                        }}
                                        checkedChildren="Find Minimum Stores"
                                        unCheckedChildren="Use Fixed Store Count"
                                        style={{ width: '100%' }}
                                      />
                                    </Tooltip>
                                    {!findMinStore && (
                                      <>
                                        <InputNumber
                                          min={1}
                                          value={minStore}
                                          onChange={(value) => {
                                            setMinStore(value);
                                            setPreviousMinStore(value);
                                          }}
                                          addonBefore="Min Store Count"
                                          className="w-full"
                                          disabled={findMinStore}
                                        />
                                        <InputNumber
                                          min={1}
                                          value={maxStore}
                                          onChange={(value) => {
                                            setMaxStore(value);
                                            setPreviousMaxStore(value);
                                          }}
                                          addonBefore="Max Store Count"
                                          className="w-full"
                                          disabled={findMinStore}
                                        />
                                      </>
                                    )}
                                  </Space>
                                </Card>
                              </Col>

                              <Col span={12}>
                                <Card
                                  size="small"
                                  title="Card Matching Preferences"
                                  extra={
                                    <Tooltip title="When enabled, cards must exactly match your preferred quality, language, and version. Disable to allow fallback options with small penalties.">
                                      <Tag color={strictPreferences ? 'red' : 'green'}>
                                        {strictPreferences ? 'Strict' : 'Flexible'}
                                      </Tag>
                                    </Tooltip>
                                  }
                                >
                                  <Switch
                                    checked={strictPreferences}
                                    onChange={setStrictPreferences}
                                    checkedChildren="Strict Preferences"
                                    unCheckedChildren="Flexible Preferences"
                                    style={{ width: '100%' }}
                                  />
                                </Card>
                              </Col>
                            </Row>

                            <InputNumber
                              min={60}
                              step={60}
                              value={minAge}
                              onChange={setMinAge}
                              addonBefore="Refresh Age"
                              addonAfter="sec"
                              className="w-full"
                            />

                            {findMinStore && strictPreferences && (
                              <Alert
                                message="Strict preferences may prevent finding a minimum-store solution."
                                description="Enable flexible preferences to allow fallback listings and improve feasibility."
                                type="warning"
                                showIcon
                              />
                            )}
                          </Space>
                        </Col>
                        <Col span={12}>
                          <div style={{ maxWidth: '600px', width: '100%', height: '500px', margin: '0 auto' }}>
                            <RadarChart weights={weights} weightConfig={weightConfig} />
                          </div>
                        </Col>
                      </Row>
                    </Panel>
                  </Collapse>
                </Col>
            </Row>
          </Panel>
        </Collapse>

      {(isOptimizing || isOptimizationComplete) && (
        <div style={{ marginBottom: '24px' }}>
          <BeautifulProgressDisplay 
            taskStatus={taskStatus}
            taskProgress={taskProgress}
            taskDetails={taskDetails}
            taskId={taskId}
            isComplete={isOptimizationComplete}
            onViewResults={optimizationResult ? handleViewResults : null}
          />

          {/* Subtask Progress */}
          {isOptimizing && !isOptimizationComplete && subtasks && (
            <SubtaskProgress subtasks={subtasks} theme={theme} />
          )}
          
          {/* Show algorithm performance info during optimization */}
          {isOptimizing && taskDetails?.algorithm_used && (
            <Alert
              message={
                <Space>
                  <ExperimentOutlined />
                  <Text strong>Algorithm: {taskDetails.algorithm_used}</Text>
                  {taskDetails.algorithm_used.toLowerCase().includes('nsga-iii') && (
                    <Tag color="blue" size="small">Reference Points</Tag>
                  )}
                </Space>
              }
              type="info"
              showIcon={false}
              style={{ marginTop: '16px' }}
            />
          )}
          
          <Divider />
        </div>
      )}

      {optimizationResult && (
        <div id="optimization-results" className="mt-8" style={{ 
          background: 'linear-gradient(135deg, #f6ffed 0%, #fcffe6 100%)',
          padding: '24px',
          borderRadius: '12px',
          border: '2px solid #b7eb8f',
          marginBottom: '24px'
        }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '16px' 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <TrophyOutlined style={{ fontSize: '32px', color: '#52c41a' }} />
              <Title level={2} style={{ margin: 0, color: '#52c41a' }}>
                Optimization Results
              </Title>
              {optimizationResult.algorithm_used && (
                <Tag color="blue" style={{ fontSize: '14px' }}>
                  {optimizationResult.algorithm_used}
                </Tag>
              )}
            </div>
            
            <Button 
              type="primary" 
              icon={<EyeOutlined />}
              size="large"
              onClick={handleGoToResultsPage}
              style={{
                background: 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)',
                border: 'none',
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(82, 196, 26, 0.3)'
              }}
            >
              View in Results Page
            </Button>
          </div>
          
          {/* optimization summary */}
          <OptimizationSummary 
            result={optimizationResult} 
            onCardClick={handleCardClick}
          />
          
          {/* Show best solution summary with metrics */}
          {optimizationResult.best_solution && (
            <div className="mt-4">
              <Title level={4}>Solution Performance</Title>
              <Space wrap>
                <Tag color="blue" icon={<ShopOutlined />} style={{ fontSize: '14px', padding: '4px 8px' }}>
                  {optimizationResult.best_solution.number_store} Stores
                </Tag>
                <Tag 
                  color={optimizationResult.best_solution.missing_cards_count === 0 ? 'green' : 'orange'} 
                  icon={optimizationResult.best_solution.missing_cards_count === 0 ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
                  style={{ fontSize: '14px', padding: '4px 8px' }}
                >
                  {optimizationResult.best_solution.missing_cards_count === 0 ? 'Complete' : 
                    `${((optimizationResult.best_solution.nbr_card_in_solution / optimizationResult.best_solution.cards_required_total) * 100).toFixed(1)}%`
                  }
                </Tag>
                <Tag color="gold" icon={<DollarOutlined />} style={{ fontSize: '14px', padding: '4px 8px' }}>
                  ${optimizationResult.best_solution.total_price.toFixed(2)}
                </Tag>
                <Tag color="purple" style={{ fontSize: '14px', padding: '4px 8px' }}>
                  {optimizationResult.best_solution.nbr_card_in_solution}/{optimizationResult.best_solution.cards_required_total} Cards
                </Tag>
                {optimizationResult.execution_time && (
                  <Tag color="cyan" style={{ fontSize: '14px', padding: '4px 8px' }}>
                    {optimizationResult.execution_time.toFixed(2)}s
                  </Tag>
                )}
                {optimizationResult.iterations && (
                  <Tag color="lime" style={{ fontSize: '14px', padding: '4px 8px' }}>
                    {optimizationResult.iterations} Iterations
                  </Tag>
                )}
                {/* Show NSGA-III specific metrics if available */}
                {optimizationResult.performance_stats?.reference_points_used && (
                  <Tag color="geekblue" style={{ fontSize: '14px', padding: '4px 8px' }}>
                    {optimizationResult.performance_stats.reference_points_used} Reference Points
                  </Tag>
                )}
                {optimizationResult.performance_stats?.diversity_metric && (
                  <Tag color="purple" style={{ fontSize: '14px', padding: '4px 8px' }}>
                    Diversity: {(optimizationResult.performance_stats.diversity_metric * 100).toFixed(1)}%
                  </Tag>
                )}
              </Space>
            </div>
          )}
          
          <div style={{ 
            marginTop: '16px', 
            padding: '12px', 
            background: 'rgba(255, 255, 255, 0.7)', 
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <Text type="secondary">
              💡 This optimization has been saved to your history. Visit the 
              <Button type="link" onClick={handleGoToResultsPage} style={{ padding: '0 4px' }}>
                Results Page
              </Button>
              to view all your optimizations and compare different algorithms and approaches.
            </Text>
          </div>
        </div>
      )}

      <Row gutter={16} className="mt-8">
        <Col span={12}>
          <Card 
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>MTG Card List</span>
                <Select
                  labelInValue
                  style={{ width: 200 }}
                  placeholder="Select Buylist"
                  value={selectedBuylist ? { value: selectedBuylist.buylistId, label: selectedBuylist.name } : null}
                  onChange={(option) => {
                    setSelectedBuylist({ buylistId: option.value, name: option.label });
                  }}
                >
                  {buylists.map(buylist => (
                    <Option key={buylist.id} value={buylist.id}>
                      {buylist.name}
                    </Option>
                  ))}
                </Select>
              </div>
            } 
            className={`ant-card ${theme}`}
          >
            <List
              bordered
              dataSource={cards}
              renderItem={card => (
                <List.Item 
                  className={`list-item hover:bg-gray-100 ${theme}`} 
                  onClick={() => handleCardClick(card)}
                >
                  {card.name}
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card 
            title={
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Site List ({selectedSiteCount})</span>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <Select 
                      value={countryFilter} 
                      onChange={setCountryFilter} 
                      style={{ width: 150 }}
                      size="small"
                    >
                      <Option value="all">All Countries ({sites.filter(s => s.active).length})</Option>
                      <Option value="usa">USA ({getCountryCounts().usa || 0})</Option>
                      <Option value="canada">Canada ({getCountryCounts().canada || 0})</Option>
                    </Select>
                    <Select 
                      mode="multiple"
                      value={methodFilter}
                      onChange={setMethodFilter}
                      style={{ width: 200 }}
                      size="small"
                      maxTagCount="responsive"
                    >
                      <Option value="all">All Platforms</Option>
                      <Option value="crystal">Crystal ({getMethodCounts().crystal || 0})</Option>
                      <Option value="shopify">Shopify ({getMethodCounts().shopify || 0})</Option>
                      <Option value="f2f">F2F ({getMethodCounts().f2f || 0})</Option>
                    </Select>
                    <Select 
                      value={siteType} 
                      onChange={setSiteType} 
                      style={{ width: 200 }}
                      size="small"
                    >
                      <Option value="primary">Primary Sites</Option>
                      <Option value="extended">Primary + Extended Sites</Option>
                    </Select>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                  <Button size="small" onClick={handleSelectAll}>Select All</Button>
                  <Button size="small" onClick={handleSelectNone}>Select None</Button>
                </div>
              </div>
            } 
            className={`ant-card ${theme}`}
          >
            <List
              bordered
              dataSource={filteredSites}
              renderItem={site => (
                <List.Item 
                  className={`list-item ${theme}`}
                  actions={[
                    <Switch
                      checked={selectedSites[site.id]}
                      onChange={() => handleSiteSelect(site.id)}
                    />
                  ]}
                >
                  <List.Item.Meta
                    title={site.name}
                    description={`${site.country} - ${site.type}`}
                  />
                  {site.active ? 'Active' : 'Inactive'}
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

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

export default Optimize;