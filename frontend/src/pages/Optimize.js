import React, { useState, useEffect, useRef } from 'react';
import api from '../utils/api';
import {Alert, Button, message, Row, Col, Card, List, Modal, Switch, InputNumber, Select, Typography, Spin, Divider, Progress, Space, Tag, Tooltip, Collapse, Slider } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import NormalizedWeightSliders, { weightConfig } from '../components/NormalizedWeightSliders';

import RadarChart from '../components/RadarChart';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import SubtaskProgress from '../components/SubtaskProgress';
import { useBuylistState } from '../hooks/useBuylistState';
import { useFetchScryfallCard } from '../hooks/useFetchScryfallCard';
import ScryfallCardView from '../components/Shared/ScryfallCardView';

const { Title, Text } = Typography;

const { Panel } = Collapse;

const Optimize = () => {
  const { theme } = useTheme();
  const { Option } = Select;

  const [cards, setCards] = useState([]);
  const [selectedCard, setSelectedCard] = useState({});

  const [sites, setSites] = useState([]);
  const [siteType, setSiteType] = useState('extended');
  const [selectedSites, setSelectedSites] = useState({});

  const [optimizationStrategy, setOptimizationStrategy] = useState('hybrid');
  const [isOptimizing, setIsOptimizing] = useState(false);
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
      message.warning('All weights are maxed — this may lead to conflicting optimization goals.');
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
  }, [weights]);

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
      setTaskDetails(response.data.details ?? null); // ← this line fixes it

      // Extract subtasks from the response
      if (response.data.current && response.data.current.subtasks) {
        setSubtasks(response.data.current.subtasks);
      }
      if (response.data.state === 'SUCCESS' || response.data.state === 'FAILURE') {
        setIsOptimizing(false);
        setTaskId(null);
        setSubtasks(null);
        localStorage.removeItem('mtg_task_id');
        if (response.data.state === 'SUCCESS') {
          message.success('Optimization completed successfully!');
          setOptimizationResult(response.data.result?.optimization);
        } else {
          message.error(`Optimization failed: ${response.data.error}`);
        }
      }
    } catch (error) {
      console.error('Error checking task status:', error);
      setIsOptimizing(false);
      setTaskId(null);
      setSubtasks(null);
    }
  };

  const fetchSites = async () => {
    try {
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
    } catch (error) {
      console.error('Error fetching sites:', error);
      message.error('Failed to fetch sites');
    }
  };

  const fetchBuylists = async () => {
    try {
      const response = await api.get('/buylists');
      setBuylists(response.data);
    } catch (error) {
      console.error('Error fetching buylists:', error);
      message.error('Failed to fetch buylists');
    }
  };

  const handleOptimize = async () => {
    try {
      const sitesToOptimize = filteredSites
        .filter(site => selectedSites[site.id])
        .map(site => site.id.toString());

      if (sitesToOptimize.length === 0) {
        message.warning('Please select at least one site to optimize');
        return;
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
      message.success(`Optimization task started with ${sitesToOptimize.length} sites!`);
    } catch (error) {
      message.error('Failed to start optimization task');
      console.error('Error during optimization:', error);
    }
  };

  const handleSelectBuylist = async (buylistId) => {
    try {
      const response = await api.get(`/buylists/${buylistId}`);
      setCards(response.data);
      message.success('Buylist selected successfully');
    } catch (error) {
      message.error('Failed to select buylist');
    }
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
      message.error('Failed to fetch card data');
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

      {isOptimizing && (
        <>
          <Progress percent={Math.round(taskProgress)} status="active" />
          <Text>{taskStatus}</Text>
          {taskDetails && <pre>{JSON.stringify(taskDetails, null, 2)}</pre>}
          {subtasks && <SubtaskProgress subtasks={subtasks} theme={theme} />}
          <Divider />
        </>
      )}

      {optimizationResult && (
        <div className="mt-8">
          <OptimizationSummary 
            result={optimizationResult} 
            onCardClick={handleCardClick}
          />
          <div className="mt-4">
            <Title level={4}>Best Solution</Title>
            <Space>
              <Tag color="blue">{`${optimizationResult.best_solution.number_store} Stores`}</Tag>
              <Tag color={optimizationResult.best_solution.completeness ? 'green' : 'orange'}>
                {optimizationResult.best_solution.completeness ? 'Complete' : `${optimizationResult.best_solution.percentage}%`}
              </Tag>
              <Text>${optimizationResult.best_solution.total_price.toFixed(2)}</Text>
            </Space>
          </div>
          <div className="mt-4">
            <Title level={4}>Iteration</Title>
            <Space>
              <Tag color="blue">{`Iteration ${optimizationResult.best_solution.iteration}`}</Tag>
            </Space>
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