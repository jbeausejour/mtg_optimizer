import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Spin, Card, Tag, Typography, Button } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import { OptimizationSummary } from '../components/OptimizationDisplay';
import api from '../utils/api';

const { Title } = Typography;

const Results = () => {
  const [opt_results, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedOptimizationResult, setSelectedOptimizationResult] = useState(null);
  const { theme } = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    fetchScans();
  }, []);

  const fetchScans = async () => {
    try {
      const response = await api.get('/results');
      setScans(response.data);
    } catch (error) {
      console.error('Error fetching optmization results:', error);
    } finally {
      setLoading(false);
    }
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
        const solution = record.optimization?.optimization?.solutions?.[0];
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
        const solution = record.optimization?.optimization?.solutions?.[0];
        if (!solution) return <Tag color="red">Failed</Tag>;
        
        const completeness = solution.nbr_card_in_solution === (solution.total_qty || solution.nbr_card_in_solution);
        const percentage = ((solution.nbr_card_in_solution / (solution.total_qty || solution.nbr_card_in_solution)) * 100).toFixed(2);
        
        return (
          <Tag color={completeness ? 'green' : 'orange'}>
            {completeness ? 'COMPLETE' : `${percentage}%`}
          </Tag>
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
          <OptimizationSummary result={selectedOptimizationResult.optimization?.optimization} />
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
    </div>
  );
};

export default Results;