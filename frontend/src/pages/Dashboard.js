import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, List, Button, Typography, Statistic, Space, Badge, Tag } from 'antd';
import { ScanOutlined, ShoppingOutlined, FieldTimeOutlined, DollarOutlined, ShopOutlined } from '@ant-design/icons';
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
        
        // Simplify the filter condition
        const validOptimizations = optimizationsRes.data.filter(opt => 
          opt.solutions?.length > 0
        );
        
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
    console.log('Processing result:', result);
    const solutions = result.solutions;
    if (!solutions || solutions.length === 0) {
        console.log('No valid solutions found');
        return null;
    }
    
    const solution = solutions[0];
    return {
        totalPrice: Number(solution.total_price || 0).toFixed(2),
        storesUsed: solution.number_store || 0,
        cardsFound: solution.nbr_card_in_solution || 0,
        totalQty: solution.total_qty || solution.nbr_card_in_solution || 0,
        missedCards: solution.missing_cards?.length || 0
    };
};

  const renderScanItem = (scan) => (
    <List.Item>
      <Card 
        hoverable 
        style={{ width: '100%' }}
        onClick={() => navigate(`/price-tracker`)}
      >
        <Space align="start">
          <Badge count={scan.sites_scraped}>
            <ScanOutlined style={{ fontSize: '24px', marginRight: '12px' }} />
          </Badge>
          <div>
            <Typography.Title level={5} style={{ margin: 0 }}>
              Scan #{scan.id}
            </Typography.Title>
            <Typography.Text type="secondary">
              <FieldTimeOutlined /> {formatDate(scan.created_at)}
            </Typography.Text>
            <br />
            <Typography.Text>
              <ShopOutlined /> {scan.cards_scraped} cards scanned
            </Typography.Text>
          </div>
        </Space>
      </Card>
    </List.Item>
  );

  const renderOptimizationItem = (optimization) => {
    const summary = renderOptimizationSummary(optimization);
    if (!summary) return null;

    let statusColor = '#52c41a'; // green by default
    if (optimization.status === 'failed') {
      statusColor = '#f5222d'; // red
    } else if (summary.missedCards > 0) {
      statusColor = '#faad14'; // orange
    }

    return (
      <List.Item>
        <Card 
          hoverable 
          style={{ width: '100%' }}
          onClick={() => navigate(`/results/${optimization.id}`)}
        >
          <Space align="start">
            <Badge 
              count={
                <Space>
                  <span>{summary.cardsFound}/{summary.totalQty}</span>
                </Space>
              }
              style={{ backgroundColor: statusColor }}
            >
              <ShoppingOutlined style={{ fontSize: '24px', marginRight: '12px' }} />
            </Badge>
            <div>
              <Space align="center">
                <Typography.Title level={5} style={{ margin: 0 }}>
                  Optimization #{optimization.id}
                </Typography.Title>
                <Tag color={statusColor}>
                  {optimization.status === 'failed' ? 'FAILED' : 
                   summary.missedCards > 0 ? 'PARTIAL' : 'COMPLETE'}
                </Tag>
              </Space>
              <Typography.Text type="secondary">
                <FieldTimeOutlined /> {formatDate(optimization.created_at)}
              </Typography.Text>
              <br />
              <Space>
                <Statistic 
                  value={summary.totalPrice} 
                  prefix={<DollarOutlined />} 
                  precision={2}
                  valueStyle={{ fontSize: '14px' }}
                />
                <Statistic
                  value={summary.storesUsed}
                  prefix={<ShopOutlined />}
                  suffix="stores"
                  valueStyle={{ fontSize: '14px' }}
                />
              </Space>
              {optimization.message && (
                <div>
                  <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                    {optimization.message}
                  </Typography.Text>
                </div>
              )}
            </div>
          </Space>
        </Card>
      </List.Item>
    );
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
        <Col span={12}>
          <Card 
            title={
              <Space>
                <ScanOutlined />
                Latest Scans
              </Space>
            } 
            extra={<Button type="link" onClick={() => navigate('/price-tracker')}>View All</Button>}
          >
            <List
              dataSource={latestScans}
              renderItem={renderScanItem}
              split={false}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card 
            title={
              <Space>
                <ShoppingOutlined />
                Latest Optimizations
              </Space>
            }
            extra={<Button type="link" onClick={() => navigate('/results')}>View All</Button>}
            loading={loading}
          >
            {latestOptimizations.length > 0 ? (
              <List
                dataSource={latestOptimizations}
                renderItem={renderOptimizationItem}
                split={false}
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