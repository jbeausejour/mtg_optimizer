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
  EyeOutlined  
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
  Collapse


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

  const [optimizationStrategy, setOptimizationStrategy] = useState('hybrid');
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
  const [minAge, setMinAge] = useState(3600);  // default 30 minutes
  const [strictPreferences, setStrictPreferences] = useState(false);
  const defaultWeights = { cost: 1.0, quality: 1.0, availability: 100.0, store_count: 0.3 };
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

  const presets = {
    cheapest: {
      cost: 10.0,
      quality: 0.1,
      availability: 10,
      store_count: 0.1,
    },
    best_quality: {
      cost: 0.1,
      quality: 10.0,
      availability: 10,
      store_count: 0.1,
    },
    high_availability: {
      cost: 2.0,
      quality: 2.0,
      availability: 1000,
      store_count: 0.1,
    },
    fewest_stores: {
      cost: 1.0,
      quality: 1.0,
      availability: 50,
      store_count: 5.0,
    },
  };
  
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
    const selectedWeights = presets[presetKey] || weights;
    setWeights(selectedWeights);
    setPresetMode(presetKey);
  };

  useEffect(() => {
    const allMaxed = Object.entries(weights).every(([key, val]) => {
      const max = key === 'availability' ? 200 : 5;
      return val >= max;
    });
  
    // Avoid setting the same value or spamming messages
    if (allMaxed && !window.__allWeightsWarned) {
      messageApi.warning('All weights are maxed — this may lead to conflicting optimization goals.');
      window.__allWeightsWarned = true;
    } else if (!allMaxed) {
      window.__allWeightsWarned = false;
    }
  
    // Save only if different
    const current = localStorage.getItem('mtg_weights');
    const next = JSON.stringify(weights);
    if (current !== next) {
      localStorage.setItem('mtg_weights', next);
    }
  }, [weights, messageApi.warning]);

  const findMinStoretooltipContent = (
    <div>
      <p><strong>When enabled:</strong> The algorithm tries to minimize the number of stores needed to fulfill the wishlist, starting from one and going up, prioritizing feasibility and cost efficiency.</p>
      <p><strong>When disabled:</strong> It uses the fixed <code>min_store</code> value from the config, without trying to reduce store count further—useful when the user prefers a specific number of stores.</p>
    </div>
  );


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

      // Extract subtasks from the response
      if (response.data.current && response.data.current.subtasks) {
        setSubtasks(response.data.current.subtasks);
      }
      
      if (response.data.state === 'SUCCESS' || response.data.state === 'FAILURE') {
        setIsOptimizing(false);
        setSubtasks(null);
        localStorage.removeItem('mtg_task_id');
        
        if (response.data.state === 'SUCCESS') {
          notificationApi.success({
            message: 'Optimization completed successfully',
            placement: 'topRight',
          });
          
          // The result is directly in response.data.result (not .optimization)
          const optimizationData = response.data.result;
          
          console.log('Setting optimization result:', optimizationData);
          
          // Add best_solution property by finding it from solutions array
          if (optimizationData && optimizationData.solutions) {
            const bestSolution = optimizationData.solutions.find(s => s.is_best_solution);
            optimizationData.best_solution = bestSolution;
          }
          
          setOptimizationResult(optimizationData);
          setIsOptimizationComplete(true);
          
          // Keep taskId for a bit longer to show the success summary
          setTimeout(() => {
            setTaskId(null);
            setIsOptimizationComplete(false);
          }, 10000); // Show success summary for 10 seconds
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

  // Add this function to handle viewing results:
  const handleViewResults = () => {
    if (optimizationResult) {
      // Scroll to results section
      const resultsElement = document.getElementById('optimization-results');
      if (resultsElement) {
        resultsElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      
      // Optional: Navigate to a dedicated results page
      navigate('/results');
    }
  };
  const handleGoToResultsPage = () => {
    navigate('/results', { 
      state: { 
        fromOptimization: true,
        optimizationId: optimizationResult?.id // if you have the result ID
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

        let minStoreValue = minStore;
        let maxStoreValue = maxStore;
        if (findMinStore) {
          minStoreValue = 1;
          maxStoreValue = 0;  
        }

        const response = await api.post('/start_scraping', {
          sites: sitesToOptimize,
          strategy: optimizationStrategy,
          min_store: minStoreValue,
          max_store: maxStoreValue,
          find_min_store: findMinStore,
          min_age_seconds: minAge,
          buylist_id: selectedBuylist?.buylistId,
          strict_preferences: strictPreferences,
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
          weights: weights,
        });

        setTaskId(response.data.task_id);
        setIsOptimizing(true);
        setSubtasks(null);
        localStorage.setItem('mtg_task_id', response.data.task_id);
        
        return { taskId: response.data.task_id, siteCount: sitesToOptimize.length };
      },
      {
        operation: 'start',
        item: 'optimization',
        loadingMessage: 'Starting optimization...',
        onSuccess: (result) => {
          messageApi.info(`Optimization task started with ${result.siteCount} sites!`);
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
      setIsModalVisible(false);    // Close modal on error
    } finally {
      setIsModalLoading(false);    // Stop spinner
    }
  };

  const handleSaveEdit = (updatedData) => {
    // console.log('[Optimize] Saved card data:', updatedData);
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
  

  return (
    <div className={`optimize section ${theme}`}>
      <h1>Optimize</h1>
      
      <Row gutter={[16, 8]} className="mb-4">
        <Col span={6}>
          <Select value={optimizationStrategy} onChange={setOptimizationStrategy} className="w-full">
            <Option value="milp">MILP</Option>
            <Option value="nsga-ii">NSGA-II</Option>
            <Option value="hybrid">Hybrid</Option>
          </Select>
          <Button 
            type="primary" 
            onClick={handleOptimize} 
            className={`optimize-button ${theme}`}
            disabled={isOptimizing || !!taskId}
          >
            {isOptimizing ? 'Optimization in Progress...' : 'Run Optimization'}
          </Button>
          {taskId && (
            <Button 
              danger 
              onClick={() => cancelTask(taskId)}
              style={{ marginLeft: '8px' }}
            >
              Cancel Task
            </Button>
          )}
        </Col>
        <Col span={24}>
          <Collapse defaultActiveKey={['1']}>
          <Panel header={<p><strong>Optimization Weights and Config</strong></p>} key="1">
            <Row gutter={16}>
              <Col span={12}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Select
                    value={presetMode}
                    onChange={handlePresetChange}
                    style={{ width: 240 }}
                  >
                    <Option value="custom">🎛 Custom (Manual sliders)</Option>
                    <Option value="cheapest">💸 Cheapest</Option>
                    <Option value="best_quality">✨ Best Quality</Option>
                    <Option value="high_availability">📦 High Availability</Option>
                    <Option value="fewest_stores">📬 Fewest Stores</Option>
                  </Select>
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
                    <Card size="small" title="Preset Values">
                      <p><strong>Cost:</strong> {presets[presetMode]?.cost ?? 0}</p>
                      <p><strong>Quality:</strong> {presets[presetMode]?.quality ?? 0}</p>
                      <p><strong>Availability:</strong> {presets[presetMode]?.availability ?? 0}</p>
                      <p><strong>Store Count:</strong> {presets[presetMode]?.store_count ?? 0}</p>
                    </Card>
                  )}
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
                                setFindMinStore(checked);
                              }}
                              checkedChildren="Find Minimum Stores"
                              unCheckedChildren="Use Fixed Store Count"
                              style={{ width: '100%' }}
                            />
                          </Tooltip>
                          {!findMinStore && (
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
                          )}
                          {!findMinStore && (
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

          {/* Subtask Progress - only show during optimization, not after completion */}
          {isOptimizing && !isOptimizationComplete && subtasks && (
            <SubtaskProgress subtasks={subtasks} theme={theme} />
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
          
          {/* Render the optimization summary */}
          <OptimizationSummary 
            result={optimizationResult} 
            onCardClick={handleCardClick}
          />
          
          {/* Show best solution summary */}
          {optimizationResult.best_solution && (
            <div className="mt-4">
              <Title level={4}>Best Solution Summary</Title>
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
                    `${((optimizationResult.best_solution.nbr_card_in_solution / optimizationResult.best_solution.total_qty) * 100).toFixed(1)}%`
                  }
                </Tag>
                <Tag color="gold" icon={<DollarOutlined />} style={{ fontSize: '14px', padding: '4px 8px' }}>
                  ${optimizationResult.best_solution.total_price.toFixed(2)}
                </Tag>
                <Tag color="purple" style={{ fontSize: '14px', padding: '4px 8px' }}>
                  {optimizationResult.best_solution.nbr_card_in_solution}/{optimizationResult.best_solution.total_qty} Cards
                </Tag>
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
              to view all your optimizations and compare different runs.
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