// File: src/components/Results.js
import React, { useState, useEffect, useContext } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Table } from 'antd';
import axios from 'axios';
import ThemeContext from '../utils/ThemeContext';
import '../global.css';

const Results = () => {
  const { scanId } = useParams();
  const [scan, setScan] = useState(null);
  const { theme } = useContext(ThemeContext);

  useEffect(() => {
    axios.get(`${process.env.REACT_APP_API_URL}/results/${scanId}`)
      .then(response => setScan(response.data))
      .catch(error => console.error('Error fetching results:', error));
  }, [scanId]);

  const columns = [
    {
      title: 'Card Name',
      dataIndex: ['Original_Card', 'Name'],
      key: 'card_name',
    },
    {
      title: 'Quantity',
      dataIndex: 'Quantity',
      key: 'quantity',
    },
    {
      title: 'Price',
      dataIndex: 'Price',
      key: 'price',
      render: (price) => `$${price.toFixed(2)}`,
    },
    {
      title: 'Total Price',
      dataIndex: 'Total Price',
      key: 'total_price',
      render: (price) => `$${price.toFixed(2)}`,
    },
    {
      title: 'Site',
      dataIndex: 'Store',
      key: 'site',
    },
  ];

  if (!scan) return <div>Loading...</div>;

  return (
    <div className={`results section ${theme}`}>
      <h1>Optimization Results</h1>
      <Card title={`Scan Date: ${new Date(scan.date).toLocaleString()}`}>
        <Table dataSource={scan.sorted_results_df} columns={columns} />
      </Card>
    </div>
  );
};

export default Results;