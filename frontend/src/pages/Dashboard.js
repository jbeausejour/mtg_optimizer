import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, List, Button, Typography, Statistic } from 'antd';
import api from '../utils/api';
import { useTheme } from '../utils/ThemeContext';

const { Title } = Typography;

const Dashboard = () => {
  const [totalSites, setTotalSites] = useState(0);
  const [totalCards, setTotalCards] = useState(0);
  const [latestScans, setLatestScans] = useState([]);
  const [latestOptimizations, setLatestOptimizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { theme } = useTheme();

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [sitesRes, cardsRes, scansRes, optimizationsRes] = await Promise.all([
          api.get('/sites'),
          api.get('/cards'),
          api.get('/scans?limit=5'),
          api.get('/results?limit=5')
        ]);

        setTotalSites(sitesRes.data.length);
        setTotalCards(cardsRes.data.length);
        setLatestScans(scansRes.data);
        
        // Process optimization results
        const validOptimizations = optimizationsRes.data.filter(opt => 
          opt.optimization?.solutions?.length > 0
        );
        console.log('Optimization results:', validOptimizations); // Debug log
        setLatestOptimizations(validOptimizations);
        
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleCardClick = (path) => {
    navigate(path);
  };

  const renderOptimizationSummary = (result) => {
    if (!result?.optimization?.solutions?.[0]) {
      console.log('No valid solution found for:', result); // Debug log
      return null;
    }
    
    const solution = result.optimization.solutions[0];
    return {
      totalPrice: Number(solution.total_price).toFixed(2),
      storesUsed: solution.number_store,
      cardsFound: solution.nbr_card_in_solution,
      totalCards: solution.total_qty || solution.nbr_card_in_solution
    };
  };

  return (
    <div className={`dashboard section ${theme}`}>
      <Title level={2}>Dashboard</Title>
      <Row gutter={[16, 16]}>
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
            onClick={() => handleCardClick('/card-management')}
            style={{ cursor: 'pointer' }}
          >
            {totalCards}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Latest Scans" bordered={false}>
            <List
              bordered
              dataSource={latestScans}
              renderItem={scan => (
                <List.Item>
                  <Button 
                    type="link" 
                    onClick={() => navigate(`/price-tracker`)}
                    style={{ width: '100%', textAlign: 'left' }}
                  >
                    #{scan.id} - {formatDate(scan.created_at)}
                    <br />
                    <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                      Scanned: {scan.cards_scraped} cards from {scan.sites_scraped} sites
                    </Typography.Text>
                  </Button>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Latest Optimizations" loading={loading}>
            {latestOptimizations.length > 0 ? (
              <List
                bordered
                dataSource={latestOptimizations}
                renderItem={optimization => {
                  const summary = renderOptimizationSummary(optimization);
                  return (
                    <List.Item>
                      <Button 
                        type="link" 
                        onClick={() => navigate(`/results/${optimization.id}`)}
                        style={{ width: '100%', textAlign: 'left' }}
                      >
                        #{optimization.id} - {formatDate(optimization.created_at)}
                        <br />
                        <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                          {summary ? (
                            <>
                              Found: {summary.cardsFound}/{summary.totalCards} cards
                              {` • Total: $${summary.totalPrice}`}
                              {` • Stores: ${summary.storesUsed}`}
                            </>
                          ) : 'No solution available'}
                        </Typography.Text>
                      </Button>
                    </List.Item>
                  );
                }}
              />
            ) : (
              <Typography.Text type="secondary">
                No optimizations available
              </Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;