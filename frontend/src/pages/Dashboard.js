import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, List, Button, Typography, Statistic, Space, Badge, Tag, Spin } from 'antd';
import { ScanOutlined, ShoppingOutlined, FieldTimeOutlined, DollarOutlined, ShopOutlined } from '@ant-design/icons';
import { useQuery} from '@tanstack/react-query';
import api from '../utils/api';
import { useTheme } from '../utils/ThemeContext';

const { Title } = Typography; 


const Dashboard = ({ userId }) => {
  const navigate = useNavigate();
  const { theme } = useTheme();

  // Use React Query for caching and automatic refetching
  const { data: sitesData } = useQuery({
    queryKey: ['sites', userId],
    queryFn: () => api.get('/sites', { params: { user_id: userId } }).then(res => res.data),
    staleTime: 300000
  });
  
  
  const { data: buylistsData } = useQuery({
    queryKey: ['buylists', userId],
    queryFn: () => api.get('/buylists', { params: { user_id: userId } }).then(res => res.data),
    staleTime: 300000
  });
  
  
  const { data: scansData, isLoading: scansLoading } = useQuery({
    queryKey: ['scans', userId],
    queryFn: () => api.get('/scans', { params: { user_id: userId, limit: 3 } }).then(res => res.data),
    staleTime: 300000
  });
  
  
  const { data: optimizationsData, isLoading: optimizationsLoading } = useQuery({
    queryKey: ['optimizations', userId],
    queryFn: () => api.get('/results', { params: { user_id: userId, limit: 3 } }).then(res => {
      const validOptimizations = res.data.filter(opt => opt.solutions?.length > 0);
      return validOptimizations;
    }),
    staleTime: 300000
  });
  
  
  const { data: topBuylistsData } = useQuery({
    queryKey: ['topBuylists', userId],
    queryFn: () => api.get('/buylists/top', { params: { user_id: userId } }).then(res => res.data),
    staleTime: 300000
  });
  

  const loading = scansLoading || optimizationsLoading;
  const totalSites = sitesData?.length || 0;
  const totalBuylists = buylistsData?.length || 0;

  const formatDate = (input) => {
    if (!input) return '—';
  
    try {
      const date = new Date(input);
      if (isNaN(date)) return input; // fallback for unparsable input
  
      const new_date = new Intl.DateTimeFormat('en-CA', {
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(date);
      return new_date;
    } catch (err) {
      console.error('Error formatting date:', err);
      return input;
    }
  };
  

  const handleNavigation = (path, state) => {
    navigate(path, { state });
  };

  // Memoize this function to avoid recalculating on every render
  const renderOptimizationSummary = React.useCallback((result) => {
    const solutions = result.solutions;
    if (!solutions || solutions.length === 0) {
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
  }, []);

  const renderScanItem = (scan) => (
    <List.Item>
      <Card 
        hoverable 
        style={{ width: '100%' }}
        onClick={() => handleNavigation(`/price-tracker`)}
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
          onClick={(e) => {
            if (e.target.tagName.toLowerCase() === 'a') {
              // Don't navigate if clicking card name
              e.stopPropagation();
              return;
            }
            handleNavigation(`/results/${optimization.id}`);
          }}
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
            variant="outlined"
            onClick={() => handleNavigation('/site-management')}
            style={{ cursor: 'pointer' }}
          >
            {totalSites}
          </Card>
        </Col>
        <Col span={8}>
          <Card 
            title="Total Buylists" 
            variant="outlined"
            onClick={() => handleNavigation('/buylist-management')}
            style={{ cursor: 'pointer' }}
          >
            {totalBuylists}
          </Card>
        </Col>
        <Col span={8}>
          <Card 
            title="Top 3 Buylists" 
            variant="outlined"
            onClick={() => handleNavigation('/buylist-management')}
            style={{ cursor: 'pointer' }}
          >
            {topBuylistsData ? (
              <List
                dataSource={topBuylistsData}
                renderItem={item => (
                  <List.Item>
                    <Button 
                      type="link" 
                      onClick={(e) => {
                        e.stopPropagation();
                        handleNavigation('/buylist-management', { 
                          buylistName: item.name,
                          buylistId: item.id
                        });
                      }}
                    >
                      {item.name}
                    </Button>
                  </List.Item>
                )}
              />
            ) : (
              <Spin size="small" />
            )}
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
            extra={<Button type="link" onClick={() => handleNavigation('/price-tracker')}>View All</Button>}
            loading={scansLoading}
          >
            {scansData && scansData.length > 0 ? (
              <List
                dataSource={scansData}
                renderItem={renderScanItem}
                split={false}
              />
            ) : !scansLoading && (
              <Typography.Text type="secondary">
                No scans available
              </Typography.Text>
            )}
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
            extra={<Button type="link" onClick={() => handleNavigation('/results')}>View All</Button>}
            loading={optimizationsLoading}
          >
            {optimizationsData && optimizationsData.length > 0 ? (
              <List
                dataSource={optimizationsData}
                renderItem={renderOptimizationItem}
                split={false}
              />
            ) : !optimizationsLoading && (
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