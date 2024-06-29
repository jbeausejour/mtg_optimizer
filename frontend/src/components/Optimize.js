import React, { useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { Button, message, Row, Col, Card, List, Modal } from 'antd';
import ThemeContext from './ThemeContext';
import '../global.css';

const Optimize = () => {
  const [cards, setCards] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [cardData, setCardData] = useState(null);
  const { theme } = useContext(ThemeContext);

  useEffect(() => {
    axios.get('/api/v1/cards')
      .then(response => setCards(response.data))
      .catch(error => console.error('Error fetching cards:', error));

    axios.get('/api/v1/sites')
      .then(response => setSites(response.data))
      .catch(error => console.error('Error fetching sites:', error));
  }, []);

  const handleOptimize = async () => {
    try {
      const response = await axios.post('/api/v1/optimize');
      message.success('Optimization completed successfully!');
    } catch (error) {
      message.error('Optimization failed!');
      console.error('Error during optimization:', error);
    }
  };

  const handleCardClick = async (card) => {
    setSelectedCard(card);
    try {
      const response = await axios.get(`/api/v1/fetch_card?name=${card.card}`);
      setCardData(response.data);
      setIsModalVisible(true);
    } catch (error) {
      console.error('Error fetching card data:', error);
    }
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
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
                  {card.Name}
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
                <List.Item className={`list-item custom-hover-row ${theme}`}>
                  {site.name}
                </List.Item>
              )}
              className={`ant-table ${theme}`}
            />
          </Card>
        </Col>
      </Row>
      <Modal
        title={selectedCard ? selectedCard.card : ''}
        visible={isModalVisible}
        onCancel={handleModalClose}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Close
          </Button>
        ]}
      >
        {cardData && (
          <div>
            <Card title="Scryfall Data" className={`ant-card ${theme}`}>
              <pre>{JSON.stringify(cardData.scryfall, null, 2)}</pre>
            </Card>
            <Card title="MTGStocks Data" className={`ant-card ${theme}`}>
              <pre>{JSON.stringify(cardData.mtgstocks, null, 2)}</pre>
            </Card>
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