import React, { useState, useEffect } from 'react';
import { Button, message, Row, Col, Card, List, Modal } from 'antd';
import CardForm from './CardForm';

const Optimize = () => {
  const [cards, setCards] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);

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

  const handleCardClick = (card) => {
    setSelectedCard(card);
    setIsModalVisible(true);
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
  };

  return (
    <div>
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
        <CardForm />
      </Modal>
    </div>
  );
};

export default Optimize;
