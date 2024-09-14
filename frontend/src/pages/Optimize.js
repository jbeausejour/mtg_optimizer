import React, { useState, useEffect, useContext } from 'react';
import api from '../utils/api';
import { Button, message, Row, Col, Card, List, Modal, Switch, InputNumber, Select, Descriptions, Image, Tag, Typography, Table, Spin, Divider, Space } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import CardListInput from '../components/CardManagement/CardListInput';
import { LinkOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const formatCardName = (name) => {
  if (!name) return '';
  const part = name.split(' // ')[0]; // Take the first part if split by ' // '
  const noApostrophes = part.replace(/'/g, ''); // Remove apostrophes
  const formatted = noApostrophes.replace(/\s+/g, '-').toLowerCase(); // Replace spaces with hyphens and convert to lowercase
  return formatted;
};

const formatSetCode = (setCode) => {
  let formattedSetCode = setCode;
  if (formattedSetCode.length > 3 && (formattedSetCode.startsWith('p') || formattedSetCode.startsWith('t'))) {
    formattedSetCode = formattedSetCode.slice(1);
  }
  return formattedSetCode.toLowerCase();
};

const formatOracleText = (text) => {
  if (!text) return null; // Return null or an appropriate fallback if text is undefined or empty
  return text.split('\n').map((paragraph, index) => (
    <Paragraph key={index}>
      {paragraph.split(/(\{[^}]+\})/).map((part, i) => (
        part.startsWith('{') ? <ManaSymbol key={i} symbol={part} /> : part
      ))}
    </Paragraph>
  ));
};

const ManaSymbol = ({ symbol }) => {
  const cleanSymbol = symbol.replace(/[{/}]/g, '');
  const symbolUrl = `https://svgs.scryfall.io/card-symbols/${cleanSymbol}.svg`;
  return (
    <img 
      src={symbolUrl} 
      alt={cleanSymbol} 
      className="mana-symbol" 
      style={{width: '16px', height: '16px', margin: '0 1px', verticalAlign: 'text-bottom'}} 
    />
  );
};

const SetSymbol = ({ setCode, rarity }) => {
  const formattedSetCode = formatSetCode(setCode);
  const symbolUrl = `https://svgs.scryfall.io/sets/${formattedSetCode}.svg`;
  const rarityColor = {
    common: 'black',
    uncommon: 'silver',
    rare: 'gold',
    mythic: '#D37E2A'
  };

  return (
    <img 
      src={symbolUrl} 
      alt={formattedSetCode} 
      className="set-symbol" 
      style={{
        width: '16px', 
        height: '16px', 
        marginRight: '4px', 
        verticalAlign: 'text-bottom',
        filter: `brightness(0) saturate(100%) ${rarityColor[rarity]}`
      }} 
    />
  );
};

const LegalityTag = ({ format, legality }) => {
  const color = {
    legal: 'green',
    not_legal: 'lightgray',
    banned: 'red',
    restricted: 'blue'
  };
  return (
    <Tag color={color[legality]}>
      {format}
    </Tag>
  );
};

const ScryfallCard = ({ data }) => {
  if (!data) return <div>No card data available</div>;

  return (
    <Card className="scryfall-card">
      <Row gutter={16}>
        <Col span={8}>
          {data.image_uris && data.image_uris.normal ? (
            <Image src={data.image_uris.normal} alt={data.name} />
          ) : (
            <div>No image available</div>
          )}
          <Divider />
          <Space direction="vertical" size="small">
            <Text><strong>Mana Value:</strong> {data.cmc}</Text>
            <Text><strong>Types:</strong> {data.type_line}</Text>
            <Text><strong>Rarity:</strong> {data.rarity}</Text>
            <Text>
              <strong>Expansion:</strong> <SetSymbol setCode={data.set} rarity={data.rarity} /> {data.set_name}
            </Text>
            <Text><strong>Card Number:</strong> {data.collector_number}</Text>
            <Text><strong>Artist:</strong> {data.artist}</Text>
          </Space>
          <Divider />
          <Title level={5}>All Printings</Title>
          <List
            dataSource={data.all_parts || []}
            renderItem={item => (
              <List.Item>
                <a href={item.scryfall_uri} target="_blank" rel="noopener noreferrer">
                  <SetSymbol setCode={item.set} rarity={item.rarity} />
                  {item.set_name} ({formatSetCode(item.set)}) - ${item.prices?.usd || 'N/A'}
                </a>
                {/* <Switch onChange={() => onVersionChange(item)} /> */}
              </List.Item>
            )}
          />
          <Divider />
          <Space direction="vertical">
            <a href={`https://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid=${data.multiverse_ids[0]}`} target="_blank" rel="noopener noreferrer">
              <LinkOutlined /> View on Gatherer
            </a>
            <a href={`https://edhrec.com/cards/${formatCardName(data.name)}`} target="_blank" rel="noopener noreferrer">
              <LinkOutlined /> Card analysis on EDHREC
            </a> 
          </Space>
        </Col>
        <Col span={16}>
          <Title level={3}>
            {data.name}
            <span className="mana-cost">
              {data.mana_cost && data.mana_cost.split('').map((char, index) => 
                char === '{' || char === '}' ? null : <ManaSymbol key={index} symbol={`{${char}}`} />
              )}
            </span>
          </Title>
          <Text strong>{data.set_name} ({data.set.toUpperCase()})</Text>
          <Divider />
          <Text>{data.type_line}</Text>
          {formatOracleText(data.oracle_text)}
          {data.flavor_text && <Text italic>{data.flavor_text}</Text>}
          <Text>{data.power && data.toughness ? `${data.power}/${data.toughness}` : ''}</Text>
          <Divider />
          <Row gutter={[8, 8]}>
            {Object.entries(data.legalities).map(([format, legality]) => (
              <Col key={format}>
                <LegalityTag format={format} legality={legality} />
              </Col>
            ))}
          </Row>
        </Col>
      </Row>
    </Card>
  );
};

const Optimize = () => {
  const [cards, setCards] = useState([]);
  const [sites, setSites] = useState([]);
  const [cardList, setCardList] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [cardData, setCardData] = useState(null);
  const [selectedSites, setSelectedSites] = useState({});
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const { theme } = useTheme();
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
      const response = await api.get('/cards');
      setCards(response.data);
    } catch (error) {
      console.error('Error fetching cards:', error);
      message.error('Failed to fetch cards');
    }
  };

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

  const handleOptimize = async () => {
    try {
      const sitesToOptimize = Object.keys(selectedSites).filter(id => selectedSites[id]);
      const response = await api.post('/start_scraping', {
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
      const response = await api.get('/task_status/${id}');
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

  const handleCardListSubmit = async (newCardList) => {
    try {
      await api.post('/card_list', { cardList: newCardList });
      message.success('Card list submitted successfully');
      setCardList(newCardList);
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
      const response = await api.get('/fetch_card?name=${card.name}');
      
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
      <CardListInput onSubmit={handleCardListSubmit} cardList={cardList} />
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
