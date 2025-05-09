import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient} from '@tanstack/react-query';
import { Card, Typography, Button, Spin, Modal, message, Space, Popconfirm, Input, Checkbox } from 'antd';
import { DeleteOutlined, SearchOutlined, ClearOutlined } from '@ant-design/icons';
import { useTheme } from '../utils/ThemeContext';
import { 
  getStandardTableColumns, 
  getColumnSearchProps, 
  getNumericFilterProps
} from '../utils/tableConfig';
import api from '../utils/api';
import { useFetchScryfallCard } from '../hooks/useFetchScryfallCard';
import ScryfallCardView from '../components/Shared/ScryfallCardView';
import EnhancedTable from '../components/EnhancedTable';
import { useEnhancedTableHandler } from '../utils/enhancedTableHandler';
import ColumnSelector from '../components/ColumnSelector';
import { ExportOptions } from '../utils/exportUtils';

const { Title, Text } = Typography;

const PriceTracker = ({ userId }) => {
  const { theme } = useTheme();
  const [selectedScan, setSelectedScan] = useState(null);
  const [selectedCard, setSelectedCard] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [modalMode, setModalMode] = useState('view');
  const queryClient = useQueryClient();

  const [cardData, setFetchedCard] = useState(null);
  const {
    mutateAsync: fetchCard,
  } = useFetchScryfallCard();

  // Use our enhanced table handler for the main scans table
  const {
    filteredInfo,
    sortedInfo,
    pagination,
    selectedIds: selectedScanIds,
    setSelectedIds: setSelectedScanIds,
    searchInput,
    visibleColumns,
    handleTableChange,
    handleSearch,
    handleReset,
    handleResetAllFilters,
    resetSelection,
    handleColumnVisibilityChange
  } = useEnhancedTableHandler({
    visibleColumns: [
      'id', 'created_at', 'cards_scraped', 'sites_scraped', 'actions'
    ]
  }, 'price_tracker_table');
  
  // Table state for scan details
  const {
    filteredInfo: detailFilteredInfo,
    sortedInfo: detailSortedInfo,
    pagination: detailPagination,
    searchInput: detailSearchInput,
    handleTableChange: handleDetailTableChange,
    handleSearch: handleDetailSearch,
    handleReset: handleDetailReset,
    handleResetAllFilters: handleDetailResetAllFilters,
  } = useEnhancedTableHandler({}, 'price_tracker_detail_table');
  
  // React Query to fetch scans
  const { data: scans = [], isLoading: scansLoading } = useQuery({
    queryKey: ['scans', userId],
    queryFn: () => api.get('/scans', { params: { user_id: userId } }).then(res => res.data),
    staleTime: 300000
  })
  
  // React Query to fetch scan details (when a scan is selected)
  const { data: selectedScanDetails, isLoading: detailsLoading } = useQuery({
    queryKey: ['scanDetails', userId, selectedScan?.id],
    queryFn: () => api.get(`/scans/${selectedScan.id}`, { params: { user_id: userId } }).then(res => res.data),
    enabled: !!selectedScan?.id,
    staleTime: 300000
  })
  
  // Mutation to delete a scan
  const deleteScanMutation = useMutation({
    mutationFn: (scanId) => api.delete(`/scans/${scanId}`, { params: { user_id: userId } }),
      // Optimistic update - remove the item immediately from UI
    onMutate: async (scanId) => {
      // Cancel any outgoing refetches so they don't overwrite our optimistic update
      await queryClient.cancelQueries(['scans', userId]);
      
      // Save the previous value
      const previousScans = queryClient.getQueryData(['scans', userId]);
      
      // Optimistically update to the new value
      queryClient.setQueryData(['scans', userId], old => 
        old.filter(scan => scan.id !== scanId)
      );
      
      // Return the previous value in case of rollback
      return { previousScans };
    },
    onError: (err, scanId, context) => {
      // Roll back to the previous value if there's an error
      queryClient.setQueryData(['scans', userId], context.previousScans);
      message.error('Failed to delete scan.');
    },
    onSettled: () => {
      // Always refetch after error or success to make sure the server state
      // and client state are in sync
      queryClient.invalidateQueries(['scans', userId]);
    }
  });
  
  const handleDelete = useCallback((scanId) => {
    setSelectedScan(null);
    deleteScanMutation.mutate(scanId);
  }, [deleteScanMutation]);

  const handleCardClick = async (card) => {
    setSelectedCard(card);
    setModalMode('view');
    setFetchedCard(null);
    setIsModalVisible(true);
  
    try {
      const data = await fetchCard({
        name: card.name,
        set_code: card.set || card.set_code || '',
        language: card.language || 'en',
        version: card.version || 'Standard',
        user_id: userId,
      });
      const enrichedCard = {
        ...card,
        ...data,
      };
      setFetchedCard(enrichedCard);
    } catch (err) {
      message.error('Failed to fetch card data');
      setIsModalVisible(false);    // Close modal on error
    } finally {
      setIsModalLoading(false);    // Stop spinner
    }
  };

  const handleSaveEdit = (updatedData) => {
    // console.log('[PriceTracker] Saved card data:', updatedData);
    setIsModalVisible(false);
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
    setFetchedCard(null);
  };

  const formatDate = (input) => {
    if (!input) return '—';
  
    try {
      const date = new Date(input);
      if (isNaN(date))
      {
        // console.log("incorrect date:", input); 
        return input; // fallback for unparsable input
      }

      const new_date = new Intl.DateTimeFormat('en-CA', {
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(date);
      return new_date;
    } catch (err) {
      console.error('Error formatting date:', err);
      return input;
    }
  };
  
  // Handle bulk deletion
  const handleBulkDelete = useCallback(async () => {
    if (selectedScanIds.size === 0) {
      message.warning('No scans selected for deletion.');
      return;
    }
    

    try {
      const scanIdList = Array.from(selectedScanIds);
      // console.log("🔥 Sending bulk delete payload:", scanIdList);
      await api.delete('/scans', {
        data: {
          user_id: userId,
          scan_ids: scanIdList
        }
      });
  
      setSelectedScanIds(new Set());
      message.success(`Successfully deleted ${scanIdList.length} scan(s).`);
      queryClient.invalidateQueries(['scans', userId]);
    } catch (error) {
      console.error('Bulk deletion error:', error);
      message.error('Failed to delete some or all of the selected scans.');
      queryClient.invalidateQueries(['scans', userId]);
    }
  }, [selectedScanIds, setSelectedScanIds, queryClient, userId]);
  
  // Define columns for the scans table using the new utility functions
  const scanColumns = useMemo(() => {
    const baseColumns = [
      {
        title: 'Scan ID',
        dataIndex: 'id',
        key: 'id',
        sorter: (a, b) => a.id - b.id,
        sortOrder: sortedInfo.columnKey === 'id' && sortedInfo.order,
        ...getNumericFilterProps('id', searchInput, filteredInfo, 'Search scan ID', handleSearch, handleReset),
      },
      {
        title: 'Date',
        dataIndex: 'created_at',
        key: 'created_at',
        render: (text) => formatDate(text),
        sorter: (a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0),
        sortOrder: sortedInfo.columnKey === 'created_at' && sortedInfo.order,
        filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
          <div style={{ padding: 8 }}>
            <Input
              type="date"
              placeholder="Search date"
              value={selectedKeys[0]}
              onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
              onPressEnter={() => handleSearch(selectedKeys, confirm, 'created_at')}
              style={{ width: 188, marginBottom: 8, display: 'block' }}
              ref={el => (searchInput.current['created_at'] = el)}
            />
            <Space>
              <Button
                type="primary"
                onClick={() => handleSearch(selectedKeys, confirm, 'created_at')}
                icon={<SearchOutlined />}
                size="small"
                style={{ width: 90 }}
              >
                Search
              </Button>
              <Button
                onClick={() => handleReset(clearFilters, 'created_at')}
                size="small"
                style={{ width: 90 }}
              >
                Reset
              </Button>
            </Space>
          </div>
        ),
        onFilter: (value, record) => {
          if (!record.created_at) return false;
          const recordDate = new Date(record.created_at).toISOString().split('T')[0];
          return recordDate === value;
        },
        filteredValue: filteredInfo.created_at || null,
      },
      {
        title: 'Cards Scanned',
        dataIndex: 'cards_scraped',
        key: 'cards_scraped',
        sorter: (a, b) => parseInt(a.cards_scraped || 0, 10) - parseInt(b.cards_scraped || 0, 10),
        sortOrder: sortedInfo.columnKey === 'cards_scraped' && sortedInfo.order,
        filters: [
          { text: 'Small (<10)', value: 'small' },
          { text: 'Medium (10-50)', value: 'medium' },
          { text: 'Large (>50)', value: 'large' }
        ],
        onFilter: (value, record) => {
          // First handle the predefined filters
          const count = parseInt(record.cards_scraped || 0, 10);
          if (value === 'small') return count < 10;
          if (value === 'medium') return count >= 10 && count <= 50;
          if (value === 'large') return count > 50;
          
          // If it's a direct numeric input (not one of the predefined filters)
          if (!isNaN(parseInt(value, 10))) {
            return count === parseInt(value, 10);
          }
          
          return false;
        },
        filteredValue: filteredInfo.cards_scraped || null,
        filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
          <div style={{ padding: 8 }}>
            <Input
              type="number"
              ref={node => {
                if (node) {
                  searchInput.current['cards_scraped'] = node;
                  setTimeout(() => node.focus(), 10);
                }
              }}
              placeholder="Search by count"
              value={selectedKeys[0]}
              onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
              onPressEnter={() => handleSearch(selectedKeys, confirm, 'cards_scraped')}
              style={{ width: 188, marginBottom: 8, display: 'block' }}
            />
            <Space>
              <Button
                type="primary"
                onClick={() => handleSearch(selectedKeys, confirm, 'cards_scraped')}
                icon={<SearchOutlined />}
                size="small"
                style={{ width: 90 }}
              >
                Search
              </Button>
              <Button 
                onClick={() => handleReset(clearFilters, 'cards_scraped')}
                size="small"
                style={{ width: 90 }}
              >
                Reset
              </Button>
            </Space>
          </div>
        ),
        filterDropdownProps: {
          onOpenChange: visible => {
            if (visible && searchInput.current['cards_scraped']) {
              setTimeout(() => searchInput.current['cards_scraped'].focus(), 10);
            }
          }
        },
      },
      {
        title: 'Sites Scanned',
        dataIndex: 'sites_scraped',
        key: 'sites_scraped',
        sorter: (a, b) => parseInt(a.sites_scraped || 0, 10) - parseInt(b.sites_scraped || 0, 10),
        sortOrder: sortedInfo.columnKey === 'sites_scraped' && sortedInfo.order,
        filters: [
          { text: 'Few (<5)', value: 'few' },
          { text: 'Several (5-15)', value: 'several' },
          { text: 'Many (>15)', value: 'many' }
        ],
        onFilter: (value, record) => {
          // First handle the predefined filters
          const count = parseInt(record.sites_scraped || 0, 10);
          if (value === 'few') return count < 5;
          if (value === 'several') return count >= 5 && count <= 15;
          if (value === 'many') return count > 15;
          
          // If it's a direct numeric input (not one of the predefined filters)
          if (!isNaN(parseInt(value, 10))) {
            return count === parseInt(value, 10);
          }
          
          return false;
        },
        filteredValue: filteredInfo.sites_scraped || null,
        filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
          <div style={{ padding: 8 }}>
            <Input
              type="number"
              ref={node => {
                if (node) {
                  searchInput.current['sites_scraped'] = node;
                  setTimeout(() => node.focus(), 10);
                }
              }}
              placeholder="Search by sites count"
              value={selectedKeys[0]}
              onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
              onPressEnter={() => handleSearch(selectedKeys, confirm, 'sites_scraped')}
              style={{ width: 188, marginBottom: 8, display: 'block' }}
            />
            <Space>
              <Button
                type="primary"
                onClick={() => handleSearch(selectedKeys, confirm, 'sites_scraped')}
                icon={<SearchOutlined />}
                size="small"
                style={{ width: 90 }}
              >
                Search
              </Button>
              <Button 
                onClick={() => handleReset(clearFilters, 'sites_scraped')}
                size="small"
                style={{ width: 90 }}
              >
                Reset
              </Button>
            </Space>
          </div>
        ),
        filterDropdownProps: {
          onOpenChange: visible => {
            if (visible && searchInput.current['sites_scraped']) {
              setTimeout(() => searchInput.current['sites_scraped'].focus(), 10);
            }
          }
        },
      },
      {
        title: 'Action',
        key: 'actions',
        render: (_, record) => (
          <Button
            type="link"
            icon={<DeleteOutlined />}
            danger
            onClick={(e) => { e.stopPropagation(); handleDelete(record.id); }}
          >
            Delete
          </Button>
        )
      }
    ];
    return baseColumns.filter(col => visibleColumns.includes(col.key));
  }, [sortedInfo, filteredInfo, searchInput, handleSearch, handleReset, formatDate, visibleColumns, handleDelete]);
  
  return (
    <div className={`price-tracker ${theme}`}>
      <Title level={2}>Price History</Title>
      {selectedScan ? (
        <>
          <Button onClick={() => { setSelectedScan(null); resetSelection(); }} type="link" className="mb-4">
            ← Back to Scans
          </Button>
          <Card>
            {detailsLoading ? (
              <Spin size="large" />
            ) : (
              <>
                <div style={{ marginBottom: 16, textAlign: 'right' }}>
                  <Button onClick={handleDetailResetAllFilters} icon={<ClearOutlined />}>
                    Reset All Filters
                  </Button>
                </div>
                <EnhancedTable
                  dataSource={selectedScanDetails?.scan_results || []}
                  columns={getStandardTableColumns(handleCardClick, detailSearchInput, detailFilteredInfo, handleDetailSearch, handleDetailReset).concat([
                    {
                      title: 'Site',
                      dataIndex: 'site_name',
                      key: 'site_name',
                      sorter: (a, b) => (a.site_name || '').localeCompare(b.site_name || ''),
                      filteredValue: detailFilteredInfo?.site_name || null,
                      onFilter: (value, record) => record.site_name === value,
                      ...getColumnSearchProps('site_name', detailSearchInput, detailFilteredInfo, 'Search site name', handleDetailSearch, handleDetailReset),
                    },
                    {
                      title: 'Last Updated',
                      dataIndex: 'updated_at',
                      key: 'updated_at',
                      render: (text, record) => {
                        const formatted = formatDate(text);
                        // console.log("📆 Formatting date for row ID", record?.id, ":", text, "→", formatted);
                        return formatted;
                      },
                      sorter: (a, b) => new Date(a.updated_at || 0) - new Date(b.updated_at || 0),
                      ...getColumnSearchProps('updated_at', detailSearchInput, detailFilteredInfo, 'Search date', handleDetailSearch, handleDetailReset),
                    }
                  ])}
                  rowKey="id"
                  loading={detailsLoading}
                  persistStateKey="price_tracker_detail_table"
                  onRowClick={handleCardClick}
                  onChange={handleDetailTableChange}
                />
              </>
            )}
          </Card>
        </>
      ) : (
        <Card>
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
            <Space>
              <ColumnSelector 
                columns={scanColumns}
                visibleColumns={visibleColumns}
                onColumnToggle={handleColumnVisibilityChange}
                persistKey="price_tracker_columns"
              />
              <ExportOptions 
                dataSource={scans}
                columns={scanColumns}
                filename="price_scans_export"
              />
              <Button onClick={handleResetAllFilters} icon={<ClearOutlined />}>
                Reset All Filters
              </Button>
              {selectedScanIds.size > 0 && (
                  <Popconfirm
                  title={`Are you sure you want to delete ${selectedScanIds.size} selected scan(s)?`}
                  okText="Yes"
                  cancelText="No"
                  onConfirm={handleBulkDelete}
                  disabled={selectedScanIds.size === 0}
                >
                  <Button danger icon={<DeleteOutlined />} disabled={selectedScanIds.size === 0}>
                    Delete Selected ({selectedScanIds.size})
                  </Button>
                </Popconfirm>
                
              )}
            </Space>
          </div>
          <EnhancedTable
            dataSource={scans}
            columns={scanColumns}
            rowKey="id"
            loading={scansLoading}
            persistStateKey="price_tracker_table"
            rowSelectionEnabled={true}
            selectedIds={selectedScanIds}
            onSelectionChange={setSelectedScanIds}
            onRowClick={(record) => setSelectedScan(record)}
            onChange={handleTableChange}
          />
        </Card>
      )}
      
      <Modal
        key={selectedCard?.id}
        open={isModalVisible}
        onCancel={handleModalClose}
        footer={null}
        width={800}
        destroyOnClose
      >
        <Spin spinning={isModalLoading} tip="Loading card details...">
        {cardData ? (
          <ScryfallCardView
            key={`${selectedCard?.id}-${cardData.id}`}
            cardData={cardData}
            mode={modalMode}
            onSave={handleSaveEdit}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <p>No card data available</p>
          </div>
        )}
        </Spin>
      </Modal>
    </div>
  );
};

export default PriceTracker;