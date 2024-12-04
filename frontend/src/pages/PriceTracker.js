import React, { useState, useEffect, useMemo } from 'react';
import { Table, Card, Typography, Tag, Button, Spin } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import api from '../utils/api';

const { Title } = Typography;

const PriceTracker = () => {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedScan, setSelectedScan] = useState(null);
  const { theme } = useTheme();

  useEffect(() => {
    fetchScans();
  }, []);

  const fetchScans = async () => {
    try {
      const response = await api.get('/scans');
      setScans(response.data);
    } catch (error) {
      console.error('Error fetching scans:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'N/A';
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'N/A';
    }
  };

  // Helper function to get unique values for filters
  const getUniqueValues = (data, field) => {
    const uniqueValues = [...new Set(data.map(item => item[field]))];
    return uniqueValues
      .filter(value => value != null)
      .map(value => ({ text: value.toString(), value: value }));
  };

  const columns = [
    {
      title: 'Card Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <input
            placeholder="Search card name"
            value={selectedKeys[0] || ''}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            onPressEnter={confirm}
            style={{ width: 188, marginBottom: 8, display: 'block' }}
          />
          <Button 
            onClick={() => {
              confirm();
            }} 
            size="small" 
            style={{ width: 90, marginRight: 8 }}
          >
            Filter
          </Button>
          <Button 
            onClick={() => {
              clearFilters();
              confirm();
            }} 
            size="small" 
            style={{ width: 90 }}
          >
            Reset
          </Button>
        </div>
      ),
      onFilter: (value, record) => 
        record.name?.toLowerCase().includes(value.toLowerCase()),
      filterIcon: filtered => (
        <span style={{ color: filtered ? '#1890ff' : undefined }}>🔍</span>
      ),
    },
    {
      title: 'Site',
      dataIndex: 'site_name',
      key: 'site_name',
      sorter: (a, b) => a.site_name.localeCompare(b.site_name),
      onFilter: (value, record) => record.site_name === value,
    },
    {
      title: 'Price',
      dataIndex: 'price',
      key: 'price',
      render: (price) => `$${price.toFixed(2)}`,
      sorter: (a, b) => a.price - b.price,
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <input
            placeholder="Min price"
            value={selectedKeys[0]}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            onPressEnter={confirm}
            style={{ width: 100, marginRight: 8 }}
          />
          <Button onClick={confirm} size="small" style={{ marginRight: 8 }}>Filter</Button>
          <Button onClick={clearFilters} size="small">Reset</Button>
        </div>
      ),
      onFilter: (value, record) => record.price >= value,
    },
    {
      title: 'Quality',
      dataIndex: 'quality',
      key: 'quality',
      sorter: (a, b) => a.quality.localeCompare(b.quality),
      filters: [
        { text: 'NM', value: 'NM' },
        { text: 'LP', value: 'LP' },
        { text: 'MP', value: 'MP' },
        { text: 'HP', value: 'HP' },
      ],
      onFilter: (value, record) => record.quality === value,
    },
    {
      title: 'Last Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (text) => formatDate(text),
      sorter: (a, b) => new Date(a.updated_at) - new Date(b.updated_at),
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <input
            type="date"
            value={selectedKeys[0]}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            style={{ width: 188, marginBottom: 8, display: 'block' }}
          />
          <Button onClick={confirm} size="small" style={{ width: 90, marginRight: 8 }}>
            Filter
          </Button>
          <Button onClick={clearFilters} size="small" style={{ width: 90 }}>
            Reset
          </Button>
        </div>
      ),
      onFilter: (value, record) => {
        if (!record.updated_at) return false;
        const recordDate = new Date(record.updated_at).toISOString().split('T')[0];
        return recordDate === value;
      },
    }
  ];

  // Generate dynamic filters for the scan results table
  const getColumnFilters = useMemo(() => {
    if (!selectedScan?.scan_results) return columns;
    
    return columns.map(col => {
      if (col.dataIndex === 'site_name') {
        return {
          ...col,
          filters: getUniqueValues(selectedScan.scan_results, 'site_name'),
        };
      }
      if (col.dataIndex === 'quality') {
        return {
          ...col,
          filters: getUniqueValues(selectedScan.scan_results, 'quality'),
        };
      }
      return col;
    });
  }, [selectedScan]);

  // Generate dynamic filters for the scans table
  const scanColumns = useMemo(() => [
    {
      title: 'Scan ID',
      dataIndex: 'id',
      key: 'id',
      sorter: (a, b) => a.id - b.id,
      filterSearch: true,
      filters: getUniqueValues(scans, 'id'),
      onFilter: (value, record) => record.id === value,
    },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => new Date(text).toLocaleString(),
      sorter: (a, b) => new Date(a.created_at) - new Date(b.created_at),
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <input
            type="date"
            value={selectedKeys[0]}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            style={{ width: 188, marginBottom: 8, display: 'block' }}
          />
          <Button onClick={confirm} size="small" style={{ width: 90, marginRight: 8 }}>Filter</Button>
          <Button onClick={clearFilters} size="small" style={{ width: 90 }}>Reset</Button>
        </div>
      ),
      onFilter: (value, record) => {
        const recordDate = new Date(record.created_at).toISOString().split('T')[0];
        return recordDate === value;
      },
    },
    {
      title: 'Cards Scanned',
      dataIndex: 'cards_scraped',
      key: 'cards_scraped',
      sorter: (a, b) => a.cards_scraped - b.cards_scraped,
    },
    {
      title: 'Sites Scanned',
      dataIndex: 'sites_scraped',
      key: 'sites_scraped',
      sorter: (a, b) => a.sites_scraped - b.sites_scraped,
    }
  ], [scans]);

  if (loading) return <Spin size="large" />;

  return (
    <div className={`price-tracker section ${theme}`}>
      <Title level={2}>Price History</Title>
      {selectedScan ? (
        <>
          <Button onClick={() => setSelectedScan(null)} type="link" className="mb-4">
            ← Back to Scans
          </Button>
          <Card>
            <Table
              dataSource={selectedScan.scan_results}
              columns={getColumnFilters}
              rowKey="id"
            />
          </Card>
        </>
      ) : (
        <Card>
          <Table
            dataSource={scans}
            columns={scanColumns}
            rowKey="id"
            onRow={(record) => ({
              onClick: () => setSelectedScan(record),
              style: { cursor: 'pointer' }
            })}
          />
        </Card>
      )}
    </div>
  );
};

export default PriceTracker;