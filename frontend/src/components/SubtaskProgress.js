import React from 'react';
import { Card, Table, Tag, Typography, Progress, Collapse } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ClockCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Panel } = Collapse;

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
  // Calculate summary stats
  const totalSites = dataSource.length;
  const completedSites = dataSource.filter(site => site.status === 'completed').length;
  const failedSites = dataSource.filter(site => site.status === 'failed').length;
  const processingSites = dataSource.filter(site => site.status === 'processing').length;

  const headerTitle = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
      <span>Site Scraping Progress</span>
      <div style={{ display: 'flex', gap: '8px' }}>
        <Tag color="success">{completedSites} completed</Tag>
        <Tag color="processing">{processingSites} processing</Tag>
        {failedSites > 0 && <Tag color="error">{failedSites} failed</Tag>}
        <Tag color="default">{totalSites} total</Tag>
      </div>
    </div>
  );

  return (
    <Card 
      size="small"
      style={{ marginBottom: 16 }}
    >
      <Collapse defaultActiveKey={['1']} size="small">
        <Panel header={headerTitle} key="1">
          <Table
            columns={columns}
            dataSource={dataSource}
            pagination={false}
            size="small"
          />
        </Panel>
      </Collapse>
    </Card>
  );
};

export default SubtaskProgress;