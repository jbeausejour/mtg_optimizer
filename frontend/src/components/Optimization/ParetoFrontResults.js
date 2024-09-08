// ParetoFrontResults.js
import React from 'react';
import { Table, Card } from 'antd';

const ParetoFrontResults = ({ paretoFront }) => {
  const columns = [
    {
      title: 'Total Cost',
      dataIndex: 'total_cost',
      key: 'total_cost',
      render: (value) => `$${value.toFixed(2)}`,
    },
    {
      title: 'Quality Score',
      dataIndex: 'quality_score',
      key: 'quality_score',
    },
    {
      title: 'Availability Score',
      dataIndex: 'availability_score',
      key: 'availability_score',
    },
    {
      title: 'Number of Stores',
      dataIndex: 'num_stores',
      key: 'num_stores',
    },
  ];

  return (
    <Card title="Pareto Front Results">
      <Table dataSource={paretoFront} columns={columns} />
    </Card>
  );
};

export default ParetoFrontResults;