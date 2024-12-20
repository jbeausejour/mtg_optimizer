import React, { useState, useEffect, useMemo } from 'react';
import { Table, Card, Typography, Tag, Button, Spin, Modal, message, Select } from 'antd';
import { useTheme } from '../utils/ThemeContext';
import api from '../utils/api';
import CardDetail from '../components/CardDetail';
import { getStandardTableColumns } from '../utils/tableConfig';
import ScryfallCardView from '../components/Shared/ScryfallCardView';

const { Title } = Typography;

const PriceTracker = ({ userId }) => {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedScan, setSelectedScan] = useState(null);
  const { theme } = useTheme();
  const [selectedScanDetails, setSelectedScanDetails] = useState(null);
  const [cardDetailVisible, setCardDetailVisible] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardData, setCardData] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchScans();
  }, []);

  useEffect(() => {
    if (selectedScan) {
      fetchScanDetails(selectedScan.id);
    }
  }, [selectedScan]);

  const fetchScans = async () => {
    try {
      const response = await api.get('/scans', {
        params: { user_id: userId } // Add user ID
      });
      setScans(response.data);
    } catch (error) {
      console.error('Error fetching scans:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchScanDetails = async (scanId) => {
    try {
      const response = await api.get(`/scans/${scanId}`, {
        params: { user_id: userId } // Add user ID
      });
      console.log('Scan details:', response.data);
      setSelectedScanDetails(response.data);
    } catch (error) {
      console.error('Error fetching scan details:', error);
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
    ...getStandardTableColumns((record) => {
      handleCardClick(record);
    }),
    {
      title: 'Site',
      dataIndex: 'site_name',
      key: 'site_name',
      sorter: (a, b) => a.site_name?.localeCompare(b.site_name),
      filters: getUniqueValues(scans, 'site_name'),
      onFilter: (value, record) => record.site_name === value,
      filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <Select
            mode="multiple"
            value={selectedKeys}
            onChange={keys => setSelectedKeys(keys)}
            style={{ width: '100%', marginBottom: 8 }}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                confirm();
              }
            }}
          >
            {getUniqueValues(scans, 'site_name').map(option => (
              <Select.Option key={option.value} value={option.value}>
                {option.text}
              </Select.Option>
            ))}
          </Select>
          <Button onClick={confirm} size="small" style={{ width: 90, marginRight: 8 }}>Filter</Button>
          <Button onClick={clearFilters} size="small" style={{ width: 90 }}>Reset</Button>
        </div>
      ),
      onFilter: (value, record) => record.site_name === value,
    },
    {
      title: 'Last Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (text) => formatDate(text),
      sorter: (a, b) => new Date(a.updated_at) - new Date(b.updated_at),
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
            autoFocus
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

  const handleCardClick = async (record) => {
    console.group('Card Click Flow');
    console.log('1. Initial record data:', record);
    setSelectedCard(record);
    setIsLoading(true);
    try {
      // Add set_code if it exists in the record, fallback to deriving it from set_name
      const deriveSetCode = (setName) => {
        // This is a placeholder - you might want to implement proper set name to code mapping
        // or fetch it from your backend/API
        return setName?.toLowerCase().replace(/[^a-z0-9]/g, '');
      };

      const setCode = record.set_code || record.set || deriveSetCode(record.set_name);
      console.log('2. Derived set code:', setCode);

      const params = {
        name: record.name,
        set: setCode,
        language: record.language || 'en',
        version: record.version || 'Normal',
        user_id: userId // Add user ID
      };
      
      console.log('3. Request params:', params);
      const response = await api.get('/fetch_card', { params });

      console.log('4. API response:', response.data);
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
      console.groupEnd();
    }
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
    setSelectedCard(null);
    setCardData(null);
  };

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
              dataSource={selectedScanDetails?.scan_results || []}
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
      {selectedCard && (
        <CardDetail
          cardName={selectedCard.name}
          setName={selectedCard.set_name}
          language={selectedCard.language}
          version={selectedCard.version}
          foil={selectedCard.foil}
          isModalVisible={cardDetailVisible}
          onClose={() => setCardDetailVisible(false)}
        />
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

export default PriceTracker;