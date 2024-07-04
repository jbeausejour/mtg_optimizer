import React, { useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { Button, message, Row, Col, Card, List, Modal, Switch, Descriptions, Image, Tag, Typography, Table, Spin } from 'antd';
import ThemeContext from '../utils/ThemeContext';
import CardListInput from '../components/CardListInput';
import '../global.css';
import { Select, InputNumber } from 'antd';

const { Title, Text } = Typography;
const { Option } = Select;

const ScryfallCard = ({ data }) => (
  <Card title="Scryfall Data" className="ant-card">
    <Descriptions column={2}>
      <Descriptions.Item label="Name">{data.name}</Descriptions.Item>
      <Descriptions.Item label="Mana Cost">{data.mana_cost}</Descriptions.Item>
      <Descriptions.Item label="Type">{data.type_line}</Descriptions.Item>
      <Descriptions.Item label="Set">{data.set_name}</Descriptions.Item>
      <Descriptions.Item label="Rarity">{data.rarity}</Descriptions.Item>
      <Descriptions.Item label="Artist">{data.artist}</Descriptions.Item>
    </Descriptions>
    {data.oracle_text && (
      <>
        <Title level={4}>Oracle Text</Title>
        <Text>{data.oracle_text}</Text>
      </>
    )}
    {data.power && data.toughness && (
      <Title level={4}>Power/Toughness: {data.power}/{data.toughness}</Title>
    )}
    {data.legalities && (
      <>
        <Title level={4}>Legalities</Title>
        <div>
          {Object.entries(data.legalities).map(([format, legality]) => (
            <Tag color={legality === 'legal' ? 'green' : 'red'} key={format}>
              {format}: {legality}
            </Tag>
          ))}
        </div>
      </>
    )}
    {data.prices && (
      <>
        <Title level={4}>Prices</Title>
        <Descriptions column={2}>
          {Object.entries(data.prices).map(([currency, price]) => (
            price && <Descriptions.Item label={currency.toUpperCase()} key={currency}>{price}</Descriptions.Item>
          ))}
        </Descriptions>
      </>
    )}
    {data.image_uris && data.image_uris.normal && (
      <Image src={data.image_uris.normal} alt={data.name} width={200} />
    )}
  </Card>
);

const CardConduitData = ({ data }) => (
  <Card title="CardConduit Data" className="ant-card">
    {data.map((item, index) => (
      <Card key={index} type="inner" title={`${item.card.name} - ${item.card.set.name}`} style={{ marginBottom: '10px' }}>
        <Descriptions column={2}>
          <Descriptions.Item label="Condition">{item.condition}</Descriptions.Item>
          <Descriptions.Item label="Foil">{item.is_foil ? 'Yes' : 'No'}</Descriptions.Item>
          <Descriptions.Item label="Amount">${item.amount}</Descriptions.Item>
          <Descriptions.Item label="TCG Low">${item.amount_tcg_low}</Descriptions.Item>
        </Descriptions>
        <Title level={5}>Services</Title>
        <Table 
          dataSource={Object.entries(item.services).map(([key, value]) => ({ key, ...value }))}
          columns={[
            { title: 'Service', dataIndex: 'key', key: 'service' },
            { title: 'Fee', dataIndex: 'fee', key: 'fee', render: (fee) => `$${fee}` },
            { title: 'Net', dataIndex: 'net', key: 'net', render: (net) => `$${net}` },
            { title: 'Eligible', dataIndex: 'is_eligible', key: 'eligible', render: (eligible) => eligible ? 'Yes' : 'No' },
          ]}
          pagination={false}
        />
      </Card>
    ))}
  </Card>
);

const PurchaseData = ({ data }) => (
  <Card title="Purchase Data" className="ant-card">
    <Table 
      dataSource={Object.entries(data).map(([site, price]) => ({ site, price }))}
      columns={[
        { title: 'Site', dataIndex: 'site', key: 'site' },
        { title: 'Price', dataIndex: 'price', key: 'price', render: (price) => `$${price}` },
      ]}
      pagination={false}
    />
  </Card>
);

const Optimize = () => {
  const [cards, setCards] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [cardData, setCardData] = useState(null);
  const [selectedSites, setSelectedSites] = useState({});
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const { theme } = useContext(ThemeContext);
  const [optimizationStrategy, setOptimizationStrategy] = useState('milp');
  const [minStore, setMinStore] = useState(2);
  const [findMinStore, setFindMinStore] = useState(false);
  const { Option } = Select;
  const [isLoading, setIsLoading] = useState(false);
  

  useEffect(() => {
    fetchCards();
    fetchSites();
  }, []);

  useEffect(() => {
    if (taskId) {
      const interval = setInterval(() => {
        checkTaskStatus(taskId);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [taskId]);

  const fetchCards = async () => {
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/cards`);
      setCards(response.data);
    } catch (error) {
      console.error('Error fetching cards:', error);
      message.error('Failed to fetch cards');
    }
  };

  const fetchSites = async () => {
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/sites`);
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

  const handleOptimize = async () => {
    try {
      const sitesToOptimize = Object.keys(selectedSites).filter(id => selectedSites[id]);
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/optimize`, {
        sites: sitesToOptimize,
        strategy: 'milp', // or 'nsga_ii' or 'hybrid'
        min_store: 2, // Add a state variable for this
        find_min_store: false // Add a state variable for this
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
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/task_status/${id}`);
      setTaskStatus(response.data.status);
      if (response.data.state === 'SUCCESS') {
        message.success('Optimization completed successfully!');
        setTaskId(null);
        // Redirect to the results page
        if (response.data.result && response.data.result.scan_id) {
          history.push(`/results/${response.data.result.scan_id}`);
        }
      }
    } catch (error) {
      console.error('Error checking task status:', error);
    }
  };

  const handleCardListSubmit = async (cardList) => {
    try {
      await axios.post(`${process.env.REACT_APP_API_URL}/card_list`, { cardList });
      message.success('Card list submitted successfully');
      fetchCards();
    } catch (error) {
      message.error('Failed to submit card list');
      console.error('Error submitting card list:', error);
    }
  };


  const handleCardClick = async (card) => {
    setSelectedCard(card);
    setIsLoading(true);
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/fetch_card?name=${card.name}`);
      
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

  const handleModalClose = () => {
    setIsModalVisible(false);
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
      <Button type="primary" onClick={handleOptimize} className={`optimize-button ${theme}`}>
        Run Optimization
      </Button>
      {taskStatus && <p>Task Status: {taskStatus}</p>}
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
            {cardData.cardconduit && (
              <Card title="CardConduit Data" className={`ant-card ${theme}`}>
                <pre>{JSON.stringify(cardData.cardconduit, null, 2)}</pre>
              </Card>
            )}
            {cardData.purchase_data && (
              <Card title="Purchase Data" className={`ant-card ${theme}`}>
                <pre>{JSON.stringify(cardData.purchase_data, null, 2)}</pre>
              </Card>
            )}
          </div>
        ) : null}
      </Modal>
      <Select
        value={optimizationStrategy}
        onChange={setOptimizationStrategy}
        style={{ width: 120 }}
      >
        <Option value="milp">MILP</Option>
        <Option value="nsga_ii">NSGA-II</Option>
        <Option value="hybrid">Hybrid</Option>
      </Select>
      <InputNumber
        min={1}
        value={minStore}
        onChange={setMinStore}
        style={{ marginLeft: 16 }}
      />
      <Switch
        checked={findMinStore}
        onChange={setFindMinStore}
        style={{ marginLeft: 16 }}
      />
    </div>
  );
};

export default Optimize;