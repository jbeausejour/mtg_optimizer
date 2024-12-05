import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Spin, Card, Tag, Typography, Button, Space, Modal, message } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import api from '../utils/api';
import ScryfallCardView from '../components/Shared/ScryfallCardView';

const { Title } = Typography;

const Results = () => {
  const [opt_results, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedOptimizationResult, setSelectedOptimizationResult] = useState(null);
  const { theme } = useTheme();
  const navigate = useNavigate();
  const [cardDetailVisible, setCardDetailVisible] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchScans();
  }, []);

  const fetchScans = async () => {
    try {
      const response = await api.get('/results');
      console.log('Optimization results:', response.data);
      setScans(response.data);
    } catch (error) {
      console.error('Error fetching optmization results:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCardClick = async (record) => {
    setSelectedCard(record);
    setIsLoading(true);
    try {
      const response = await api.get('/fetch_card', {
        params: {
          name: record.name,
          set: record.set || record.set_code,
          language: record.language,
          version: record.version
        }
      });

      if (!response.data?.scryfall) {
        throw new Error('Invalid data structure received from backend');
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

  const handleModalClose = () => {
    setIsModalVisible(false);
    setSelectedCard(null);
    setCardData(null);
  };

  const columns = [
    {
      title: 'Scan ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => new Date(text).toLocaleString(),
    },
    {
      title: 'Best Solution',
      key: 'best_solution',
      render: (_, record) => {
        const solution = record.solutions?.[0];
        if (!solution) return 'No solution found';
        
        return (
          <span>
            {solution.number_store} stores at ${solution.total_price.toFixed(2)} ({solution.nbr_card_in_solution}/{solution.total_qty || solution.nbr_card_in_solution} cards)
          </span>
        );
      },
    },
    {
      title: 'Status',
      key: 'status',
      render: (_, record) => {
        const solution = record.solutions?.[0];
        if (!solution) return <Tag color="red">Failed</Tag>;
        
        const completeness = solution.nbr_card_in_solution === (solution.total_qty || solution.nbr_card_in_solution);
        const percentage = ((solution.nbr_card_in_solution / (solution.total_qty || solution.nbr_card_in_solution)) * 100).toFixed(2);
        
        let color = 'green';
        let status = 'COMPLETE';

        if (record.status === 'failed') {
          color = 'red';
          status = 'FAILED';
        } else if (!completeness) {
          color = 'orange';
          status = `${percentage}% (${solution.nbr_card_in_solution}/${solution.total_qty || solution.nbr_card_in_solution})`;
        }
        
        return (
          <Space>
            <Tag color={color}>{status}</Tag>
            {record.message && (
              <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                {record.message}
              </Typography.Text>
            )}
          </Space>
        );
      },
    }
  ];

  if (loading) return <Spin size="large" />;

  return (
    <div className={`results section ${theme}`}>
      <Title level={2}>Optimization History</Title>
      {selectedOptimizationResult ? (
        <>
          <div className="mb-4">
            <Button onClick={() => setSelectedOptimizationResult(null)} type="link">
              ← Back to History
            </Button>
          </div>
          <OptimizationSummary 
            result={selectedOptimizationResult} 
            onCardClick={handleCardClick}
          />
        </>
      ) : (
        <Card>
          <Table
            dataSource={opt_results}
            columns={columns}
            rowKey="id"
            onRow={(record) => ({
              onClick: () => setSelectedOptimizationResult(record),
              style: { cursor: 'pointer' }
            })}
          />
        </Card>
      )}
      <Modal
        title={selectedCard?.name}
        open={isModalVisible}
        onCancel={handleModalClose}
        width={800}
        destroyOnClose={true}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Close
          </Button>
        ]}
      >
        {isLoading ? (
          <Spin size="large" />
        ) : cardData ? (
          <ScryfallCardView 
            key={`${selectedCard?.id}-${cardData.id}`}
            cardData={cardData}
            mode="view"
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin />
            <p>Loading card details...</p>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Results;