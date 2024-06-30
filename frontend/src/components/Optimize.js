import React, { useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { Button, message, Row, Col, Card, List, Modal, Switch, Descriptions, Image, Tag, Typography, Table } from 'antd';
import ThemeContext from './ThemeContext';
import '../global.css';

const { Title, Text } = Typography;

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
    <Title level={4}>Oracle Text</Title>
    <Text>{data.oracle_text}</Text>
    {data.power && data.toughness && (
      <Title level={4}>Power/Toughness: {data.power}/{data.toughness}</Title>
    )}
    <Title level={4}>Legalities</Title>
    <div>
      {Object.entries(data.legalities).map(([format, legality]) => (
        <Tag color={legality === 'legal' ? 'green' : 'red'} key={format}>
          {format}: {legality}
        </Tag>
      ))}
    </div>
    <Title level={4}>Prices</Title>
    <Descriptions column={2}>
      {Object.entries(data.prices).map(([currency, price]) => (
        price && <Descriptions.Item label={currency.toUpperCase()} key={currency}>{price}</Descriptions.Item>
      ))}
    </Descriptions>
    {data.image_uris && (
      <Image src={data.image_uris.normal} alt={data.name} width={200} />
    )}
  </Card>
);

const MTGStocksCard = ({ data }) => {
  const columns = [
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
    },
    {
      title: 'Price',
      dataIndex: 'price',
      key: 'price',
    },
  ];

  const priceData = Object.entries(data.prices).map(([type, price]) => ({
    key: type,
    type,
    price: `$${price}`,
  }));

  return (
    <Card title="MTGStocks Data" className="ant-card">
      <Descriptions column={1}>
        <Descriptions.Item label="Name">{data.name}</Descriptions.Item>
        <Descriptions.Item label="Set">{data.set}</Descriptions.Item>
      </Descriptions>
      <Title level={4}>Prices</Title>
      <Table columns={columns} dataSource={priceData} pagination={false} />
      <a href={data.link} target="_blank" rel="noopener noreferrer">View on MTGStocks</a>
    </Card>
  );
};

const Optimize = () => {
  const [cards, setCards] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [cardData, setCardData] = useState(null);
  const [selectedSites, setSelectedSites] = useState({});
  const { theme } = useContext(ThemeContext);

  useEffect(() => {
    fetchCards();
    fetchSites();
  }, []);

  const fetchCards = async () => {
    try {
      const response = await axios.get('/api/v1/cards');
      setCards(response.data);
    } catch (error) {
      console.error('Error fetching cards:', error);
      message.error('Failed to fetch cards');
    }
  };

  const fetchSites = async () => {
    try {
      const response = await axios.get('/api/v1/sites');
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
      const response = await axios.post('/api/v1/optimize', { sites: sitesToOptimize });
      message.success('Optimization completed successfully!');
    } catch (error) {
      message.error('Optimization failed!');
      console.error('Error during optimization:', error);
    }
  };

  const handleCardClick = async (card) => {
    setSelectedCard(card);
    try {
      const response = await axios.get(`/api/v1/fetch_card?name=${card.name}`);
      
      // Format MTGStocks data
      const mtgStocksData = response.data.mtgstocks;
      const formattedMTGStocksData = {
        name: mtgStocksData.name,
        set: mtgStocksData.set,
        link: mtgStocksData.link,
        prices: {
          market: mtgStocksData.prices.market || 'N/A',
          low: mtgStocksData.prices.low || 'N/A',
          median: mtgStocksData.prices.median || 'N/A',
          high: mtgStocksData.prices.high || 'N/A',
          foil: mtgStocksData.prices.foil || 'N/A',
          avg: mtgStocksData.prices.avg || 'N/A',
        }
      };

      setCardData({
        ...response.data,
        mtgstocks: formattedMTGStocksData
      });
      setIsModalVisible(true);
    } catch (error) {
      console.error('Error fetching card data:', error);
      message.error('Failed to fetch card data');
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
      <Button type="primary" onClick={handleOptimize} className={`optimize-button ${theme}`}>
        Run Optimization
      </Button>
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
        visible={isModalVisible}
        onCancel={handleModalClose}
        width={800}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Close
          </Button>
        ]}
      >
        {cardData && (
          <div>
            <ScryfallCard data={cardData.scryfall} />
            <MTGStocksCard data={cardData.mtgstocks} />
            {cardData.previous_scan && (
              <Card title="Previous Scan Data" className={`ant-card ${theme}`}>
                <pre>{JSON.stringify(cardData.previous_scan, null, 2)}</pre>
              </Card>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Optimize;