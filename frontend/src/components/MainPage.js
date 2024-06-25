import React, { useEffect, useState } from 'react';
import { List, Card, Row, Col } from 'antd';

const MainPage = () => {
  const [cards, setCards] = useState([]);
  const [sites, setSites] = useState([]);

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

  return (
    <div>
      <Row gutter={16}>
        <Col span={12}>
          <Card title="MTG Card List">
            <List
              bordered
              dataSource={cards}
              renderItem={card => <List.Item>{card.card}</List.Item>}
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
    </div>
  );
};

export default MainPage;
