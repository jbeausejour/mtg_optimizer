import React, { useState, useEffect, useContext } from 'react';
import { Button, message, Row, Col, Card, List, Modal } from 'antd';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import ThemeContext from './ThemeContext';
import './Optimize.css';

const Optimize = () => {
  const [cards, setCards] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [cardData, setCardData] = useState(null);
  const location = useLocation();
  const { theme } = useContext(ThemeContext);

  useEffect(() => {
    fetch('/api/cards')
      .then(response => response.json())
      .then(data => setCards(data))
      .catch(error => console.error('Error fetching cards:', error));

    fetch('/api/sites')
      .then(response => response.json())
      .then(data => setSites(data))
      .catch(error => console.error('Error fetching sites:', error));
  }, []);

  const handleOptimize = async () => {
    try {
      const response = await fetch('/api/optimize', { method: 'POST' });
      const result = await response.json();
      message.success('Optimization completed successfully!');
    } catch (error) {
      message.error('Optimization failed!');
      console.error('Error during optimization:', error);
    }
  };

  const handleCardClick = async (card) => {
    setSelectedCard(card);
    try {
      const response = await axios.get(`/fetch_card?name=${card.card}`);
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
    <div className={`optimize ${theme}`}>
      <h1>Optimize</h1>
      <Button type="primary" onClick={handleOptimize}>Run Optimization</Button>
      <Row gutter={16}>
        <Col span={12}>
          <Card title="MTG Card List">
            <List
              bordered
              dataSource={cards}
              renderItem={card => (
                <List.Item onClick={() => handleCardClick(card)}>
                  {card.card}
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Site List">
            <List
              bordered
              dataSource={sites}
              renderItem={site => <List.Item>{site.name}</List.Item>}
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
            <Card title="Scryfall Data">
              <pre>{JSON.stringify(cardData.scryfall, null, 2)}</pre>
            </Card>
            <Card title="MTGStocks Data">
              <pre>{JSON.stringify(cardData.mtgstocks, null, 2)}</pre>
            </Card>
            {cardData.previous_scan && (
              <Card title="Previous Scan Data">
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
