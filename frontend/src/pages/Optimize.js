import React, { useState, useEffect } from 'react';
import api from '../utils/api';
import { Button, message, Row, Col, Card, List, Modal, Switch, InputNumber, Select, Typography, Spin, Divider, Progress, Space, Tag, Tooltip } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import { useBuylistState } from '../hooks/useBuylistState';
import { useFetchScryfallCard } from '../hooks/useFetchScryfallCard';
import ScryfallCardView from '../components/Shared/ScryfallCardView';

const { Title, Text } = Typography;

const Optimize = ({ userId }) => {
  const [cards, setCards] = useState([]);
  const [selectedCard, setSelectedCard] = useState({});
  const [sites, setSites] = useState([]);
  const [selectedSites, setSelectedSites] = useState({});
  const [optimizationStrategy, setOptimizationStrategy] = useState('hybrid');
  const [minStore, setMinStore] = useState(15);
  const [findMinStore, setFindMinStore] = useState(true);
  const [taskId, setTaskId] = useState(null);
  const [taskState, setTaskState] = useState(null);
  const [taskDetails, setTaskDetails] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const { theme } = useTheme();
  const { Option } = Select;
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [modalMode, setModalMode] = useState('view');
  const [taskProgress, setTaskProgress] = useState(0);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [siteType, setSiteType] = useState('extended');
  const [countryFilter, setCountryFilter] = useState('canada'); 
  const [methodFilter, setMethodFilter] = useState(['all']); 
  const [selectedSiteCount, setSelectedSiteCount] = useState(0); 
  const [buylists, setBuylists] = useState([]); 
  const { selectedBuylist, setSelectedBuylist} = useBuylistState();
  const [minAge, setMinAge] = useState(1800);  // default 30 minutes
  const [strictPreferences, setStrictPreferences] = useState(false);

  const [cardData, setFetchedCard] = useState(null);
  const {
    mutateAsync: fetchCard,
  } = useFetchScryfallCard();


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
    if (userId) {
      fetchSites();
      fetchBuylists(); 
    }
  }, [userId]);

  useEffect(() => {
    if (taskId) {
      setIsOptimizing(true);
      const interval = setInterval(() => {
        checkTaskStatus(taskId);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [taskId]);

  useEffect(() => {
    if (buylists.length > 0 && !selectedBuylist) {
      const first = buylists[0];
      setSelectedBuylist({ id: first.id, name: first.name }); 
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

      if (response.data.state === 'SUCCESS' || response.data.state === 'FAILURE') {
        setIsOptimizing(false);
        setTaskId(null);
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
    }
  };

  const fetchSites = async () => {
    try {
      const response = await api.get('/sites', {
        params: { user_id: userId } 
      });
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
      const response = await api.get('/buylists', { params: { user_id: userId } });
      setBuylists(response.data);
    } catch (error) {
      console.error('Error fetching buylists:', error);
      message.error('Failed to fetch buylists');
    }
  };

  const handleOptimize = async () => {
    try {
      // console.log("Sending userId:", userId);
      const sitesToOptimize = filteredSites
        .filter(site => selectedSites[site.id])
        .map(site => site.id.toString());

      if (sitesToOptimize.length === 0) {
        message.warning('Please select at least one site to optimize');
        return;
      }
      const response = await api.post('/start_scraping', {
        sites: sitesToOptimize,
        strategy: optimizationStrategy,
        min_store: minStore,
        find_min_store: findMinStore,
        min_age_seconds: minAge,
        user_id: userId,
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
        }))
      });
      setTaskId(response.data.task_id);
      message.success(`Optimization task started with ${sitesToOptimize.length} sites!`);
    } catch (error) {
      message.error('Failed to start optimization task');
      console.error('Error during optimization:', error);
    }
  };

  const handleSelectBuylist = async (buylistId) => {
    try {
      const response = await api.get(`/buylists/${buylistId}`, {
        params: { user_id: userId }
      });
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
        version: card.version || 'Standard',
        user_id: userId,
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

  const findMinStoretooltipContent = (
    <div>
      <p><strong>When enabled:</strong> The algorithm tries to minimize the number of stores needed to fulfill the wishlist, starting from one and going up, prioritizing feasibility and cost efficiency.</p>
      <p><strong>When disabled:</strong> It uses the fixed <code>min_store</code> value from the config, without trying to reduce store count further—useful when the user prefers a specific number of stores.</p>
    </div>
  );

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
            disabled={isOptimizing}
          >
            {isOptimizing ? 'Optimization in Progress...' : 'Run Optimization'}
          </Button>
        </Col>
        <Col span={6}>
          <InputNumber
            min={1}
            value={minStore}
            onChange={setMinStore}
            className="w-full"
            addonBefore="Min Store"
          />
        </Col>
        <Col span={6}>
          <Tooltip title="Specify how old the cached data can be (in seconds) before it’s considered stale.">
            <InputNumber
              min={60}
              step={60}
              value={minAge}
              onChange={setMinAge}
              addonAfter="sec"
              addonBefore="Refresh if data is older than"
              placeholder="1800"
            />
          </Tooltip>
        </Col>      
        <Col span={6}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
            <Tooltip title={findMinStoretooltipContent}>
              <div style={{ width: 180 }}>
                <Switch
                  size="small"
                  checked={findMinStore}
                  onChange={setFindMinStore}
                  checkedChildren="Find Min Store"
                  unCheckedChildren="Don't Find Min Store"
                  style={{ width: '100%' }}
                />
              </div>
            </Tooltip>

            <Tooltip title="Strict Preferences: If enabled, only exact matches for language, set, quality, and version will be considered.">
              <div style={{ width: 180 }}>
                <Switch
                  size="small"
                  checked={strictPreferences}
                  onChange={setStrictPreferences}
                  checkedChildren="Strict Preferences"
                  unCheckedChildren="Flexible Preferences"
                  style={{ width: '100%', marginBottom: 8  }}
                />
              </div>
            </Tooltip>
          </div>
        </Col>
      </Row>

      {isOptimizing && (
        <>
          <Progress percent={Math.round(taskProgress)} status="active" />
          <Text>{taskStatus}</Text>
          {taskDetails && <pre>{JSON.stringify(taskDetails, null, 2)}</pre>}
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
                    setSelectedBuylist({ id: option.value, name: option.label });
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