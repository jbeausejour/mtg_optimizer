import React, { useState, useEffect, useContext } from 'react';
import api from '../utils/api';
import { Button, message, Row, Col, Card, List, Modal, Switch, InputNumber, Select, Typography, Spin, Divider } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import ScryfallCard from '../components/CardManagement/ScryfallCard'; 
import CardListInput from '../components/CardManagement/CardListInput';

const { Title, Text, Paragraph } = Typography;


//Main component rendering the UI for optimization tasks
const Optimize = () => {
  const [cards, setCards] = useState([]);
  const [cardData, setCardData] = useState(null);
  const [cardList, setCardList] = useState([]);

  const [selectedCard, setSelectedCard] = useState({});
  const [sites, setSites] = useState([]);
  const [selectedSites, setSelectedSites] = useState({});
  
  const [optimizationStrategy, setOptimizationStrategy] = useState('milp');
  const [minStore, setMinStore] = useState(2);
  const [findMinStore, setFindMinStore] = useState(false);

  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [optimizationResult, setOptimizationResult] = useState(null); // Stores optimization results

  const { theme } = useTheme();
  const { Option } = Select;
  const [isLoading, setIsLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);

  //Fetches the list of cards and sites when the component mounts. (Initial data load)
  useEffect(() => {
    fetchCards();
    fetchSites();
  }, []);

  //Checks task status periodically when an optimization task starts. (Triggered by taskId change)
  useEffect(() => {
    if (taskId) {
      const interval = setInterval(() => {
        checkTaskStatus(taskId);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [taskId]);

  //Fetches available cards to display in the "MTG Card List". (Initial data load)
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

  //Fetches available sites to display in the "Site List". (Initial data load)
  const fetchSites = async () => {
    try {
      const response = await api.get('/sites');
      setSites(response.data);
      const initialSelected = {};
      response.data.forEach(site => {
        initialSelected[site.id] = site.active;
      });
      setSelectedSites(initialSelected);
    } catch (error) {
      console.error('Error fetching sites:', error);
      message.error('Failed to fetch sites');
    }
  };

  // Handles the optimization request by posting the selected cards, strategy, 
  // and site information to the backend. (Triggered by the "Run Optimization" button)
  const handleOptimize = async () => {
    try {
      const sitesToOptimize = Object.keys(selectedSites).filter(id => selectedSites[id]);
      // Log to verify data before sending the request
      console.log("Sites:", sitesToOptimize);
      console.log("Strategy:", optimizationStrategy);
      console.log("Min Store:", minStore);
      console.log("Find Min Store:", findMinStore);
      console.log("Card List:", cardList);
      console.log("Sending request data:", JSON.stringify({
        sites: sitesToOptimize,
        strategy: optimizationStrategy,
        min_store: minStore,
        find_min_store: findMinStore,
        card_list: cardList,
      }));
      
      // Add cardList and strategy to the request
      const response = await api.post('/start_scraping', {
        sites: sitesToOptimize,
        strategy: optimizationStrategy, // User-selected strategy (MILP, NSGA-II, etc.)
        min_store: minStore, // Minimum store count
        find_min_store: findMinStore, // Boolean
        card_list: cardList // Add the card list to the request
      });
  
      setTaskId(response.data.task_id);
      message.success('Optimization task started!');
    } catch (error) {
      message.error('Failed to start optimization task');
      console.error('Error during optimization:', error);
    }
  };
  

  //Checks the status of the ongoing optimization task. (Triggered periodically after starting an optimization)
  const checkTaskStatus = async (id) => {
    try {
      const response = await api.get(`/task_status/${id}`);
      setTaskStatus(response.data.status);
      if (response.data.state === 'SUCCESS') {
        message.success('Optimization completed successfully!');
        setTaskId(null);
        setOptimizationResult(response.data.result); // Store the result to display
      }
    } catch (error) {
      console.error('Error checking task status:', error);
    }
  };

  //Submits the user-added card list and updates the state. (Result of user submitting a card list)
  const handleCardListSubmit = async (newCardList) => {
    try {
      await api.post('/card_list', { cardList: newCardList });
      message.success('Card list submitted successfully');
      setCards(newCardList); // Update the `cards` state
      setCardList(newCardList); // Also update the `cardList` state to keep them in sync
    } catch (error) {
      message.error('Failed to submit card list');
      console.error('Error submitting card list:', error);
    }
  };

  //Handles when a user clicks on a card, fetching detailed data for that card. (User clicks on a card from the card list)
  const handleCardClick = async (card) => {
    setSelectedCard(card);
    setIsLoading(true);
    try {
      const response = await api.get(`/fetch_card?name=${card.name}`);
      
      if (response.data.error) {
        throw new Error(response.data.error);
      }
      
      console.log('Card data:', response.data);  // For debugging

      setCardData(response.data);
      setIsModalVisible(true);
    } catch (error) {
      console.error('Error fetching card data:', error);
      message.error(`Failed to fetch card data: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  //Closes the modal that shows card details. (User closes the card details modal)
  const handleModalClose = () => {
    setIsModalVisible(false);
  };

  //Toggles whether a site is selected for optimization. (User toggles site selection switch)
  const handleSiteSelect = (siteId) => {
    setSelectedSites(prev => ({
      ...prev,
      [siteId]: !prev[siteId]
    }));
  };

  return (
    <div className={`optimize section ${theme}`}>
      <h1>Optimize</h1>
      <CardListInput onSubmit={handleCardListSubmit} CardListInput />
      <Row gutter={16} style={{ marginBottom: '20px' }}>
        <Col span={8}>
          <Select
            value={optimizationStrategy}
            onChange={setOptimizationStrategy}
            style={{ width: '100%' }}
          >
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
            style={{ width: '100%' }}
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
      {taskStatus && <p>Task Status: {taskStatus}</p>}
      {optimizationResult && (
        <div>
          <Divider />
          <Title level={4}>Optimization Results</Title>
          <pre style={{ backgroundColor: '#f0f0f0', padding: '10px', borderRadius: '5px' }}>
            {JSON.stringify(optimizationResult, null, 2)}
          </pre>
        </div>
      )}
      <Row gutter={16}>
        <Col span={12}>
          <Card title="MTG Card List" className={`ant-card ${theme}`}>
            <List
              bordered
              dataSource={cards}
              renderItem={card => (
                <List.Item 
                  className={`list-item custom-hover-row ${theme}`} 
                  onClick={() => handleCardClick(card)}
                >
                  {card.name}
                </List.Item>
              )}
              className={`ant-table ${theme}`}
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
                  className={`list-item custom-hover-row ${theme}`}
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
              className={`ant-table ${theme}`}
            />
          </Card>
        </Col>
      </Row>
      <Modal
        title={selectedCard ? selectedCard.name : ''}
        open={isModalVisible}
        onCancel={handleModalClose}
        width={800}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Close
          </Button>
        ]}
      >
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin size="large" />
            <p>Loading card data...</p>
          </div>
        ) : cardData ? (
          <div>
            <ScryfallCard data={cardData.scryfall} />
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

export default Optimize;