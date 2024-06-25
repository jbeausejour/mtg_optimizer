import React from 'react';
import { Card, Row, Col } from 'antd';

const Dashboard = () => {
  return (
    <div>
      <h1>Dashboard</h1>
      <Row gutter={16}>
        <Col span={8}>
          <Card title="Total Sites" bordered={false}>
            10
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Total Cards" bordered={false}>
            150
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Latest Scrape" bordered={false}>
            2024-06-23
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
