import React, { useState, useEffect } from 'react';
import api from '../utils/api';
import { Button, message, Row, Col, Card, List, Modal, Switch, InputNumber, Select, Typography, Spin, Divider, Progress, Space, Tag, Tooltip } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import ScryfallCard from '../components/CardManagement/ScryfallCard'; 
import { OptimizationSummary } from '../components/OptimizationDisplay';

const { Title, Text } = Typography;

const Optimize = ({ userId }) => {
  const [cards, setCards] = useState([]);
  const [cardData, setCardData] = useState(null);
  const [selectedCard, setSelectedCard] = useState({});
  const [sites, setSites] = useState([]);
  const [selectedSites, setSelectedSites] = useState({});
  const [optimizationStrategy, setOptimizationStrategy] = useState('hybrid');
  const [minStore, setMinStore] = useState(15);
  const [findMinStore, setFindMinStore] = useState(true);
  const [taskId, setTaskId] = useState(null);
  const [taskState, setTaskState] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const { theme } = useTheme();
  const { Option } = Select;
  const [isLoading, setIsLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [taskProgress, setTaskProgress] = useState(0);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [siteType, setSiteType] = useState('extended');
  const [countryFilter, setCountryFilter] = useState('canada'); 
  const [methodFilter, setMethodFilter] = useState(['all']); 
  const [selectedSiteCount, setSelectedSiteCount] = useState(0); 
  const [buylists, setBuylists] = useState([]); 
  const [selectedBuylist, setSelectedBuylist] = useState(null); 
  const [minAge, setMinAge] = useState(1800);  // default 30 minutes

  useEffect(() => {
    fetchSites();
    fetchBuylists(); // Fetch buylists on component mount
  }, []);

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
      setSelectedBuylist(buylists[0].id);
      handleSelectBuylist(buylists[0].id);
    }
  }, [buylists]);

  const fetchSites = async () => {
    try {
      const response = await api.get('/sites', {
        params: { user_id: 'your_user_id' } // Add user ID
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
        buylist_id: selectedBuylist,  
        card_list: cards.map(card => ({
          name: card.name,
          quantity: card.quantity,
          set_name: card.set_name,
          quality: card.quality
        }))
      });
      setTaskId(response.data.task_id);
      message.success(`Optimization task started with ${sitesToOptimize.length} sites!`);
    } catch (error) {
      message.error('Failed to start optimization task');
      console.error('Error during optimization:', error);
    }
  };

  const checkTaskStatus = async (id) => {
    try {
      const response = await api.get(`/task_status/${id}`);
      setTaskState(response.data.state);
      setTaskStatus(response.data.status);
      setTaskProgress(response.data.progress ?? 0);

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
    setIsLoading(true);
    try {
      const response = await api.get(`/fetch_card?name=${card.name}`);
      if (response.data.error) throw new Error(response.data.error);
      setCardData(response.data);
      setIsModalVisible(true);
    } catch (error) {
      message.error(`Failed to fetch card data: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
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

  // useEffect(() => {
  //   console.log('Current sites:', sites);
  //   console.log('Site type:', siteType);
  //   console.log('Filtered sites:', filteredSites);
  // }, [sites, siteType, selectedSites]);

  useEffect(() => {
    setSelectedSiteCount(filteredSites.filter(site => selectedSites[site.id]).length);
  }, [filteredSites, selectedSites]);

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
      <p>When find_min_store is True:</p>
      <p>
        The algorithm will perform a search to find the minimum number of stores required to fulfill the user's wishlist.
        It iterates through different store counts, starting from 1 up to the total number of unique stores available.
        For each store count, it attempts to find a feasible solution that meets the user's requirements.
        The goal is to find the solution with the fewest stores that still meets the user's wishlist, while also considering the cost.
        This approach ensures that the solution uses the minimum number of stores possible, which can be beneficial for reducing shipping costs and simplifying logistics.
      </p>
      <p>When find_min_store is False:</p>
      <p>
        The algorithm will use the min_store value provided in the configuration to set a fixed minimum number of stores that must be used.
        It does not attempt to minimize the number of stores beyond this fixed value.
        The focus is primarily on finding a feasible solution that meets the user's requirements while adhering to the specified minimum store constraint.
        This approach is useful when the user has a preference for using a certain number of stores, regardless of whether fewer stores could potentially fulfill the wishlist.
      </p>
    </div>
  );

  return (
    <div className={`optimize section ${theme}`}>
      <h1>Optimize</h1>
      
      <Row gutter={16} className="mb-4">
        <Col span={8}>
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
        
        <Col span={8}>
          <InputNumber
            min={1}
            value={minStore}
            onChange={setMinStore}
            className="w-full"
            addonBefore="Min Store"
          />
        </Col>
        <Col span={6}>
          <Tooltip title={findMinStoretooltipContent} overlayStyle={{ width: 900 }}>
            <Switch
              checked={findMinStore}
              onChange={setFindMinStore}
              checkedChildren="Find Min Store"
              unCheckedChildren="Don't Find Min Store"
            />
          </Tooltip>
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
      </Row>

      {taskState && (
        <div className="my-4">
          <Text>Task Status: {taskState}: {taskStatus}</Text>
          {taskProgress > 0 && taskProgress < 100 && (
            <Progress percent={taskProgress} status="active" />
          )}
        </div>
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
                  value={selectedBuylist} 
                  onChange={(value) => {
                    setSelectedBuylist(value);
                    handleSelectBuylist(value);
                  }} 
                  style={{ width: 200 }}
                  placeholder="Select Buylist"
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
        title={selectedCard.name}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setIsModalVisible(false)}>
            Close
          </Button>
        ]}
      >
        {isLoading ? (
          <div className="text-center p-4">
            <Spin size="large" />
            <Text className="mt-4">Loading card data...</Text>
          </div>
        ) : cardData?.scryfall ? (
          <ScryfallCard data={cardData.scryfall} />
        ) : (
          <div>No card data available</div>
        )}
      </Modal>
    </div>
  );
};

export default Optimize;