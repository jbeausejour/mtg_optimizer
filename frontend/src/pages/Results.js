import React, { useState, useEffect } from 'react';
import { Table, Spin, Card, Tag, Typography, Button, Space, Modal, message } from 'antd';
import { CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import ScryfallCardView from '../components/Shared/ScryfallCardView';
import api from '../utils/api';

const { Title, Text } = Typography;

const Results = ({ userId }) => {
  const [optimizationResults, setOptimizationResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedResult, setSelectedResult] = useState(null);
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { theme } = useTheme();

  useEffect(() => {
    fetchResults();
  }, []);

  const fetchResults = async () => {
    try {
      const response = await api.get('/results', {
        params: { user_id: userId } // Add user ID
      });
      setOptimizationResults(response.data);
    } catch (error) {
      console.error('Error fetching optimization results:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCardClick = async (card) => {
    setSelectedCard(card);
    setIsLoading(true);
    try {
      const response = await api.get('/fetch_card', {
        params: {
          name: card.name,
          set: card.set_code || card.set_name,
          language: card.language || 'English',
          version: card.version || 'Normal',
          user_id: userId // Add user ID
        }
      });

      if (!response.data?.scryfall) {
        throw new Error('Invalid card data received');
      }

      setCardData(response.data.scryfall);
      setIsModalVisible(true);
    } catch (error) {
      console.error('Error fetching card:', error);
      message.error(`Failed to fetch card details: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: text => new Date(text).toLocaleString(),
      sorter: (a, b) => new Date(b.created_at) - new Date(a.created_at),
    },
    {
      title: 'Stats',
      key: 'stats',
      render: (_, record) => (
        <Space>
          <Tag color="blue">{`${record.sites_scraped} Sites`}</Tag>
          <Tag color="purple">{`${record.cards_scraped} Cards`}</Tag>
        </Space>
      ),
    },
    {
      title: 'Best Solution',
      key: 'best_solution',
      render: (_, record) => {
        const bestSolution = record.solutions?.find(s => s.is_best_solution);
        if (!bestSolution) return <Tag color="red">No solution</Tag>;

        const completeness = bestSolution.nbr_card_in_solution === bestSolution.total_qty;
        const percentage = ((bestSolution.nbr_card_in_solution / bestSolution.total_qty) * 100).toFixed(1);

        return (
          <Space>
            <Tag color="blue">{`${bestSolution.number_store} Stores`}</Tag>
            <Tag color={completeness ? 'green' : 'orange'}>
              {completeness ? 'Complete' : `${percentage}%`}
            </Tag>
            <Text>${bestSolution.total_price.toFixed(2)}</Text>
          </Space>
        );
      },
    },
    {
      title: 'Iteration',
      key: 'iteration',
      render: (_, record) => {
        const iterationCount = record.solutions?.filter(s => !s.is_best_solution).length;
        if (!iterationCount) return <Tag color="red">No iteration</Tag>;

        return (
          <Space>
            <Tag color="blue">{`Iteration ${iterationCount}`}</Tag>
          </Space>
        );
      },
    },
    {
      title: 'Status',
      key: 'status',
      render: (_, record) => {
        const bestSolution = record.solutions?.find(s => s.is_best_solution);
        if (!bestSolution) return <Tag color="red">Failed</Tag>;
        
        if (record.status === 'Completed') {
          return <Tag color="green" icon={<CheckCircleOutlined />}>Success</Tag>;
        }
        
        return <Tag color="red" icon={<WarningOutlined />}>{record.status}</Tag>;
      },
    }
  ];

  if (loading) return <Spin size="large" />;

  return (
    <div className={`results section ${theme}`}>
      <Title level={2}>Optimization History</Title>
      
      {selectedResult ? (
        <>
          <Button 
            type="link" 
            onClick={() => setSelectedResult(null)} 
            className="mb-4"
          >
            ← Back to History
          </Button>
          <OptimizationSummary 
            result={selectedResult}
            onCardClick={handleCardClick}
          />
        </>
      ) : (
        <Card>
          <Table
            dataSource={optimizationResults}
            columns={columns}
            rowKey="id"
            onRow={record => ({
              onClick: () => setSelectedResult(record),
              style: { cursor: 'pointer' }
            })}
          />
        </Card>
      )}

      <Modal
        title={selectedCard?.name}
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          setSelectedCard(null);
          setCardData(null);
        }}
        width={800}
        footer={null}
      >
        {isLoading ? (
          <div className="text-center p-4">
            <Spin size="large" />
            <Text className="mt-4">Loading card details...</Text>
          </div>
        ) : cardData ? (
          <ScryfallCardView cardData={cardData} mode="view" />
        ) : (
          <Text>No card data available</Text>
        )}
      </Modal>
    </div>
  );
};

export default Results;