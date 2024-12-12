import React, { useState, useEffect } from 'react';
import api from '../utils/api';
import { Button, message, Row, Col, Card, List, Modal, Switch, InputNumber, Select, Typography, Spin, Divider, Progress } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import ScryfallCard from '../components/CardManagement/ScryfallCard'; 
import CardListInput from '../components/CardManagement/CardListInput';
import { OptimizationSummary } from '../components/OptimizationDisplay';

const { Title, Text } = Typography;

const Optimize = () => {
  const [cards, setCards] = useState([]);
  const [cardData, setCardData] = useState(null);
  const [cardList, setCardList] = useState([]);
  const [selectedCard, setSelectedCard] = useState({});
  const [sites, setSites] = useState([]);
  const [selectedSites, setSelectedSites] = useState({});
  const [optimizationStrategy, setOptimizationStrategy] = useState('hybrid');
  const [minStore, setMinStore] = useState(15);
  const [findMinStore, setFindMinStore] = useState(true);
  const [taskId, setTaskId] = useState(null);
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
  const [methodFilter, setMethodFilter] = useState(['all']);  // Change to array

  useEffect(() => {
    fetchCards();
    fetchSites();
  }, []);

  useEffect(() => {
    if (taskId) {
      setIsOptimizing(true);
      const interval = setInterval(() => {
        checkTaskStatus(taskId);
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [taskId]);

  const fetchCards = async () => {
    try {
      const response = await api.get('/cards');
      setCards(response.data);
      setCardList(response.data);
    } catch (error) {
      console.error('Error fetching cards:', error);
      message.error('Failed to fetch cards');
    }
  };

  // Update fetchSites to ensure type is set
  const fetchSites = async () => {
    try {
      const response = await api.get('/sites');
      // Ensure each site has a type property, default to 'primary' if not set
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

  const handleOptimize = async () => {
    try {
      // Use the already filtered sites list and only select those that are enabled
      const sitesToOptimize = filteredSites
        .filter(site => selectedSites[site.id])
        .map(site => site.id.toString());

      // Debug log to verify what's being sent
      console.log('Sites being sent for optimization:', sitesToOptimize);
      console.log('Total filtered sites:', filteredSites.length);
      console.log('Total selected sites:', sitesToOptimize.length);

      if (sitesToOptimize.length === 0) {
        message.warning('Please select at least one site to optimize');
        return;
      }

      const response = await api.post('/start_scraping', {
        sites: sitesToOptimize,
        strategy: optimizationStrategy,
        min_store: minStore,
        find_min_store: findMinStore,
        card_list: cardList.map(card => ({
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
      setTaskStatus(response.data.state);
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

  const handleCardListSubmit = async (newCardList) => {
    try {
      await api.post('/card_list', { cardList: newCardList });
      setCards(newCardList);
      setCardList(newCardList);
      message.success('Card list submitted successfully');
    } catch (error) {
      message.error('Failed to submit card list');
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
    setSelectedSites(prev => ({
      ...prev,
      [siteId]: !prev[siteId]
    }));
  };

  // Update the filteredSites logic
  const filteredSites = sites.filter(site => {
    // First check if site is active
    if (!site.active) return false;
    
    // Apply country filtering
    if (countryFilter !== 'all' && site.country?.toLowerCase() !== countryFilter) {
      return false;
    }

    // Apply type filtering - always return true for 'extended' type
    if (siteType === 'primary' && site.type?.toLowerCase() !== 'primary') {
      return false;
    }

    // Apply platform filtering - allow if 'all' is selected or method matches any selected method
    if (!methodFilter.includes('all') && !methodFilter.includes(site.method?.toLowerCase())) {
      return false;
    }

    return true;
  });

  // Get country counts for the selector
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

  // Add platform counts helper
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

  // Add useEffect to debug site filtering
  useEffect(() => {
    console.log('Current sites:', sites);
    console.log('Site type:', siteType);
    console.log('Filtered sites:', filteredSites);
  }, [sites, siteType]);

  return (
    <div className={`optimize section ${theme}`}>
      <h1>Optimize</h1>
      <CardListInput onSubmit={handleCardListSubmit} />
      
      <Row gutter={16} className="mb-4">
        <Col span={8}>
          <Select value={optimizationStrategy} onChange={setOptimizationStrategy} className="w-full">
            <Option value="milp">MILP</Option>
            <Option value="nsga-ii">NSGA-II</Option>
            <Option value="hybrid">Hybrid</Option>
          </Select>
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
        <Col span={8}>
          <Switch
            checked={findMinStore}
            onChange={setFindMinStore}
            checkedChildren="Find Min Store"
            unCheckedChildren="Don't Find Min Store"
          />
        </Col>
      </Row>

      <Button 
        type="primary" 
        onClick={handleOptimize} 
        className={`optimize-button ${theme}`}
        disabled={isOptimizing}
      >
        {isOptimizing ? 'Optimization in Progress...' : 'Run Optimization'}
      </Button>

      {taskStatus && (
        <div className="my-4">
          <Text>Task Status: {taskStatus}</Text>
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
        </div>
      )}

      <Row gutter={16} className="mt-8">
        <Col span={12}>
          <Card title="MTG Card List" className={`ant-card ${theme}`}>
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Site List ({filteredSites.length})</span>
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
                    <Option value="hawk">Hawk ({getMethodCounts().hawk || 0})</Option>
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