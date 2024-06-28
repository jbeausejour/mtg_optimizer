import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, List, Button } from 'antd';
import axios from 'axios';
import ThemeContext from '../components/ThemeContext';
import '../global.css';

const Dashboard = () => {
  const [totalSites, setTotalSites] = useState(0);
  const [totalCards, setTotalCards] = useState(0);
  const [latestScans, setLatestScans] = useState([]);
  const navigate = useNavigate();
  const { theme } = useContext(ThemeContext);

  useEffect(() => {
    axios.get('/api/v1/sites')
      .then(response => setTotalSites(response.data.length))
      .catch(error => console.error('Error fetching sites:', error));

    axios.get('/api/v1/cards')
      .then(response => setTotalCards(response.data.length))
      .catch(error => console.error('Error fetching cards:', error));

    axios.get('/api/v1/scans?limit=5')
      .then(response => setLatestScans(response.data))
      .catch(error => console.error('Error fetching scans:', error));
  }, []);
  const handleCardClick = (path) => {
    navigate(path);
  };

  return (
    <div className={`dashboard section ${theme}`}>
      <h1>Dashboard</h1>
      <Row gutter={16}>
        <Col span={8}>
          <Card 
            title="Total Sites" 
            bordered={false}
            onClick={() => handleCardClick('/site-management')}
            style={{ cursor: 'pointer' }}
          >
            {totalSites}
          </Card>
        </Col>
        <Col span={8}>
          <Card 
            title="Total Cards" 
            bordered={false}
            onClick={() => handleCardClick('/optimize')}
            style={{ cursor: 'pointer' }}
          >
            {totalCards}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Latest Scrapes" bordered={false}>
            <List
              bordered
              dataSource={latestScans}
              renderItem={scan => (
                <List.Item>
                  <Button 
                    type="link" 
                    onClick={() => handleCardClick(`/results/${scan.id}`)}
                  >
                    {scan.name} - {scan.date}
                  </Button>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
