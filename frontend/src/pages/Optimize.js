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
  const [optimizationStrategy, setOptimizationStrategy] = useState('milp');
  const [minStore, setMinStore] = useState(5);
  const [findMinStore, setFindMinStore] = useState(true);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const { theme } = useTheme();
  const { Option } = Select;
  const [isLoading, setIsLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [taskProgress, setTaskProgress] = useState(0);

  useEffect(() => {
    fetchCards();
    fetchSites();
  }, []);

  useEffect(() => {
    if (taskId) {
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

  const fetchSites = async () => {
    try {
      const response = await api.get('/sites');
      setSites(response.data);
      const initialSelected = response.data.reduce((acc, site) => ({
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
      const sitesToOptimize = Object.keys(selectedSites).filter(id => selectedSites[id]);
      const response = await api.post('/start_scraping', {
        sites: sitesToOptimize,
        strategy: optimizationStrategy,
        min_store: minStore,
        find_min_store: findMinStore,
        card_list: cardList.map(card => ({
          name: card.name,
          quantity: card.quantity,
          set_name: card.set_name,
          quality: card.quality  // Ensure quality is included
        }))
      });
      setTaskId(response.data.task_id);
      message.success('Optimization task started!');
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

      if (response.data.state === 'SUCCESS') {
        message.success('Optimization completed successfully!');
        setTaskId(null);
        setOptimizationResult(response.data.result?.optimization);
      } else if (response.data.state === 'FAILURE') {
        message.error(`Optimization failed: ${response.data.error}`);
        setTaskId(null);
      }
    } catch (error) {
      console.error('Error checking task status:', error);
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

  return (
    <div className={`optimize section ${theme}`}>
      <h1>Optimize</h1>
      <CardListInput onSubmit={handleCardListSubmit} />
      
      <Row gutter={16} className="mb-4">
        <Col span={8}>
          <Select value={optimizationStrategy} onChange={setOptimizationStrategy} className="w-full">
            <Option value="milp">MILP</Option>
            <Option value="nsga_ii">NSGA-II</Option>
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

      <Button type="primary" onClick={handleOptimize} className={`optimize-button ${theme}`}>
        Run Optimization
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
          <OptimizationSummary result={optimizationResult} />
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
          <Card title="Site List" className={`ant-card ${theme}`}>
            <List
              bordered
              dataSource={sites}
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
        ) : cardData ? (
          <ScryfallCard data={cardData.scryfall} />
        ) : null}
      </Modal>
    </div>
  );
};

export default Optimize;