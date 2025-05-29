import React from 'react';
import { Card, Progress, Tag, Typography, Space, Statistic, Row, Col, Button, Alert } from 'antd';
import { 
  DatabaseOutlined, 
  ThunderboltOutlined, 
  BarChartOutlined, 
  CheckCircleOutlined,
  ClockCircleOutlined,
  RocketOutlined,
  ShopOutlined,
  DollarOutlined,
  TrophyOutlined,
  EyeOutlined
} from '@ant-design/icons';

const { Text, Title } = Typography;


const BeautifulProgressDisplay = ({ 
  taskStatus, 
  taskProgress, 
  taskDetails, 
  taskId, 
  isComplete = false,
  onViewResults = null 
}) => {
  
  const getStepIcon = (step) => {
    const iconMap = {
      'data_preparation': <DatabaseOutlined />,
      'data_processing': <DatabaseOutlined />,
      'optimization_start': <RocketOutlined />,
      'initialization': <ClockCircleOutlined />,
      'nsga-ii': <ThunderboltOutlined />,
      'milp': <BarChartOutlined />,
      'hybrid': <ThunderboltOutlined />,
      'evaluation': <BarChartOutlined />,
      'iteration': <ThunderboltOutlined />,
      'completion': <CheckCircleOutlined />,
      'optimization_complete': <TrophyOutlined />
    };
    return iconMap[step] || <ClockCircleOutlined />;
  };

  const getStepColor = (step) => {
    const colorMap = {
      'data_preparation': 'blue',
      'data_processing': 'blue', 
      'optimization_start': 'orange',
      'initialization': 'orange',
      'nsga-ii': 'purple',
      'milp': 'green',
      'hybrid': 'magenta',
      'evaluation': 'cyan',
      'iteration': 'purple',
      'completion': 'success',
      'optimization_complete': 'success'
    };
    return colorMap[step] || 'default';
  };

  const getStepDisplayName = (step) => {
    const nameMap = {
      'data_preparation': 'Preparing Data',
      'data_processing': 'Processing Cards',
      'optimization_start': 'Starting Optimization',
      'initialization': 'Initializing',
      'nsga-ii': 'Genetic Algorithm',
      'milp': 'Mathematical Optimization',
      'hybrid': 'Hybrid Approach',
      'evaluation': 'Evaluating Solutions',
      'iteration': 'Finding Best Solution',
      'completion': 'Completing',
      'optimization_complete': 'Optimization Complete'
    };
    return nameMap[step] || step?.replace('_', ' ').toUpperCase();
  };
  const renderBeautifulStepDetails = (details) => {
    if (!details) return null;

    const { step, generation, iteration, solutions_found, best_score, cards_processed, total_cards, sites_processed, total_sites } = details;

    return (
      <div style={{ 
        background: 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)',
        padding: '16px',
        borderRadius: '8px',
        border: '1px solid #dee2e6'
      }}>
        <Row gutter={16}>
          {/* Generation/Iteration Info */}
          {(generation !== undefined || iteration !== undefined) && (
            <Col span={6}>
              <Statistic
                title={step === 'nsga-ii' ? 'Generation' : 'Iteration'}
                value={generation || iteration || 0}
                prefix={step === 'nsga-ii' ? <ThunderboltOutlined /> : <BarChartOutlined />}
                valueStyle={{ fontSize: '18px', color: '#1890ff' }}
              />
            </Col>
          )}

          {/* Solutions Found */}
          {solutions_found !== undefined && (
            <Col span={6}>
              <Statistic
                title="Solutions Found"
                value={solutions_found}
                prefix={<TrophyOutlined />}
                valueStyle={{ fontSize: '18px', color: '#52c41a' }}
              />
            </Col>
          )}

          {/* Best Score */}
          {best_score !== undefined && (
            <Col span={6}>
              <Statistic
                title="Best Score"
                value={best_score}
                precision={2}
                prefix={<BarChartOutlined />}
                valueStyle={{ fontSize: '18px', color: '#722ed1' }}
              />
            </Col>
          )}

          {/* Cards Progress */}
          {(cards_processed !== undefined && total_cards !== undefined) && (
            <Col span={6}>
              <div>
                <Text strong style={{ color: '#666', fontSize: '12px' }}>CARDS PROCESSED</Text>
                <div style={{ marginTop: '4px' }}>
                  <Text style={{ fontSize: '18px', color: '#fa8c16' }}>
                    {cards_processed}/{total_cards}
                  </Text>
                </div>
                <Progress 
                  percent={Math.round((cards_processed / total_cards) * 100)} 
                  size="small" 
                  showInfo={false}
                  strokeColor="#fa8c16"
                />
              </div>
            </Col>
          )}

          {/* Sites Progress */}
          {(sites_processed !== undefined && total_sites !== undefined) && (
            <Col span={6}>
              <div>
                <Text strong style={{ color: '#666', fontSize: '12px' }}>SITES PROCESSED</Text>
                <div style={{ marginTop: '4px' }}>
                  <Text style={{ fontSize: '18px', color: '#13c2c2' }}>
                    {sites_processed}/{total_sites}
                  </Text>
                </div>
                <Progress 
                  percent={Math.round((sites_processed / total_sites) * 100)} 
                  size="small" 
                  showInfo={false}
                  strokeColor="#13c2c2"
                />
              </div>
            </Col>
          )}
        </Row>

        {/* Additional Details */}
        {details.message && (
          <div style={{ marginTop: '12px' }}>
            <Text style={{ fontStyle: 'italic', color: '#666' }}>
              {details.message}
            </Text>
          </div>
        )}

        {/* Step-specific additional info */}
        {step === 'nsga-ii' && generation && (
          <div style={{ marginTop: '8px' }}>
            <Space size="small">
              <Tag color="purple">Genetic Evolution</Tag>
              <Text type="secondary">
                Evolving population to find optimal solutions
              </Text>
            </Space>
          </div>
        )}

        {step === 'milp' && (
          <div style={{ marginTop: '8px' }}>
            <Space size="small">
              <Tag color="green">Mathematical Solver</Tag>
              <Text type="secondary">
                Finding exact optimal solution using linear programming
              </Text>
            </Space>
          </div>
        )}

        {step === 'hybrid' && (
          <div style={{ marginTop: '8px' }}>
            <Space size="small">
              <Tag color="magenta">Hybrid Approach</Tag>
              <Text type="secondary">
                Combining genetic algorithm with mathematical optimization
              </Text>
            </Space>
          </div>
        )}
      </div>
    );
  };

  // If optimization is complete and successful, show success summary
  if (isComplete && taskDetails?.step === 'optimization_complete' && taskDetails?.best_solution) {
    const { best_solution, elapsed_time, solutions_found } = taskDetails;
    
    return (
      <Alert
        message={
          <div 
            style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              cursor: onViewResults ? 'pointer' : 'default'
            }}
            onClick={onViewResults}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <TrophyOutlined style={{ color: '#52c41a', fontSize: '20px' }} />
              <div>
                <Text strong style={{ color: '#52c41a', fontSize: '16px' }}>
                  Optimization Successful: {best_solution.number_store} stores • ${best_solution.total_price?.toFixed(2)}
                </Text>
                <div style={{ marginTop: '4px' }}>
                  <Space size="small">
                    <Tag color="success" icon={<CheckCircleOutlined />}>
                      {best_solution.nbr_card_in_solution} cards found
                    </Tag>
                    <Tag color="blue" icon={<ClockCircleOutlined />}>
                      {elapsed_time}
                    </Tag>
                    <Tag color="purple">
                      {solutions_found} solutions evaluated
                    </Tag>
                    {best_solution.missing_cards_count === 0 && (
                      <Tag color="gold" icon={<TrophyOutlined />}>
                        Complete
                      </Tag>
                    )}
                  </Space>
                </div>
              </div>
            </div>
            {onViewResults && (
              <Button 
                type="primary" 
                icon={<EyeOutlined />}
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onViewResults();
                }}
              >
                View Results
              </Button>
            )}
          </div>
        }
        type="success"
        style={{ marginBottom: '16px' }}
        showIcon={false}
      />
    );
  }

  // Alternative: If we have task completion but details structure is different
  // Show a simpler success message when optimization completes
  if (isComplete && taskStatus?.includes('completed')) {
    return (
      <Alert
        message={
          <div 
            style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              cursor: onViewResults ? 'pointer' : 'default'
            }}
            onClick={onViewResults}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <TrophyOutlined style={{ color: '#52c41a', fontSize: '20px' }} />
              <div>
                <Text strong style={{ color: '#52c41a', fontSize: '16px' }}>
                  Optimization Completed Successfully!
                </Text>
                <div style={{ marginTop: '4px' }}>
                  <Text type="secondary">Check the results below</Text>
                </div>
              </div>
            </div>
            {onViewResults && (
              <Button 
                type="primary" 
                icon={<EyeOutlined />}
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onViewResults();
                }}
              >
                View Results
              </Button>
            )}
          </div>
        }
        type="success"
        style={{ marginBottom: '16px' }}
        showIcon={false}
      />
    );
  }

  // Regular progress display for ongoing optimization
  return (
    <Card 
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Optimization Progress</span>
          <Space>
            {taskDetails?.step && (
              <Tag icon={getStepIcon(taskDetails.step)} color={getStepColor(taskDetails.step)}>
                {getStepDisplayName(taskDetails.step)}
              </Tag>
            )}
            <Tag color="processing">Task: {taskId?.slice(-8)}</Tag>
          </Space>
        </div>
      }
      size="small" 
      style={{ marginBottom: '16px' }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Main Progress Bar */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <Text strong>{taskStatus || 'Processing...'}</Text>
            <Text type="secondary">{Math.round(taskProgress)}%</Text>
          </div>
          <Progress 
            percent={Math.round(taskProgress)} 
            status="active"
            strokeColor={{
              '0%': '#1890ff',
              '100%': '#52c41a',
            }}
          />
        </div>
        
        {/* Beautiful Step-specific Details */}
        {taskDetails && renderBeautifulStepDetails(taskDetails)}
      </div>
    </Card>
  );
};

export default BeautifulProgressDisplay;