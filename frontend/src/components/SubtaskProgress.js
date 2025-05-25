import React from 'react';
import { Card, Table, Tag, Typography, Progress } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ClockCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;
// New component for displaying subtask progress
const SubtaskProgress = ({ subtasks, theme }) => {
  if (!subtasks) return null;

  const columns = [
    {
      title: 'Site',
      dataIndex: 'site_name',
      key: 'site_name',
      width: '30%',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: '15%',
      render: (status) => {
        const config = {
          pending: { color: 'default', icon: <ClockCircleOutlined /> },
          processing: { color: 'processing', icon: <LoadingOutlined spin /> },
          completed: { color: 'success', icon: <CheckCircleOutlined /> },
          failed: { color: 'error', icon: <CloseCircleOutlined /> },
        };
        const { color, icon } = config[status] || config.pending;
        return (
          <Tag color={color} icon={icon}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Tag>
        );
      },
    },
    {
      title: 'Progress',
      dataIndex: 'progress',
      key: 'progress',
      width: '25%',
      render: (progress) => (
        <Progress 
          percent={Math.round(progress)} 
          size="small" 
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
      ),
    },
    {
      title: 'Details',
      key: 'details',
      render: (_, record) => {
        if (record.status === 'completed') {
          return <Text type="success">{record.cards_found || 0} cards found</Text>;
        }
        if (record.status === 'failed') {
          return <Text type="danger">{record.error || 'Unknown error'}</Text>;
        }
        if (record.status === 'processing') {
          return (
            <Text>
              {record.details || `${record.cards_processed || 0}/${record.cards_count} cards`}
            </Text>
          );
        }
        return <Text type="secondary">Waiting...</Text>;
      },
    },
  ];

  const dataSource = Object.entries(subtasks)
  .map(([taskId, task]) => ({
    key: taskId,
    ...task,
  }))
  .sort((a, b) => {
    // Sort by progress first (descending)
    if (b.progress !== a.progress) {
      return b.progress - a.progress;
    }
    // If progress is equal, sort by cards_count (descending)
    return (b.cards_count || 0) - (a.cards_count || 0);
  });


  return (
    <Card 
      title="Site Scraping Progress" 
      size="small"
      style={{ marginBottom: 16 }}
    >
      <Table
        columns={columns}
        dataSource={dataSource}
        pagination={false}
        size="small"
      />
    </Card>
  );
};

export default SubtaskProgress;