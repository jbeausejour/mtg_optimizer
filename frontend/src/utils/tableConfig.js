import React, { useRef } from 'react';
import { Button, Input, Space } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import Highlighter from 'react-highlight-words';

// Style for card name links
const cardNameStyle = {
  color: 'inherit',
  cursor: 'pointer',
  textDecoration: 'none',
  borderBottom: '1px dotted #999',
};

/**
 * Get text filter props for table columns
 * @param {string} dataIndex - Column data index
 * @param {Object} searchInputRef - Ref object for input elements
 * @param {Object} filteredInfo - Current filter state
 * @param {string} placeholder - Input placeholder text
 * @param {Function} handleSearch - Search handler
 * @param {Function} handleReset - Reset handler
 * @returns {Object} - Column props for Ant Design Table
 */
export const getColumnSearchProps = (dataIndex, searchInputRef, filteredInfo, placeholder, handleSearch, handleReset) => ({
  filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
    <div style={{ padding: 8 }}>
      <Input
        ref={node => {
          if (node) {
            searchInputRef.current[dataIndex] = node;
            // Focus input when dropdown opens
            setTimeout(() => node.focus(), 10);
          }
        }}
        placeholder={placeholder || `Search ${dataIndex}`}
        value={selectedKeys[0]}
        onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
        onPressEnter={() => handleSearch(selectedKeys, confirm, dataIndex)}
        style={{ width: 188, marginBottom: 8, display: 'block' }}
      />
      <Space>
        <Button
          type="primary"
          onClick={() => handleSearch(selectedKeys, confirm, dataIndex)}
          icon={<SearchOutlined />}
          size="small"
          style={{ width: 90 }}
        >
          Search
        </Button>
        <Button 
          onClick={() => handleReset(clearFilters, dataIndex)}
          size="small"
          style={{ width: 90 }}
        >
          Reset
        </Button>
      </Space>
    </div>
  ),
  filterIcon: filtered => (
    <SearchOutlined style={{ color: filtered ? '#1890ff' : undefined }} />
  ),
  filteredValue: filteredInfo?.[dataIndex] || null,
  onFilter: (value, record) => 
    record[dataIndex]
      ? record[dataIndex].toString().toLowerCase().includes(value.toLowerCase())
      : '',
  onFilterDropdownVisibleChange: visible => {
    if (visible && searchInputRef.current[dataIndex]) {
      setTimeout(() => searchInputRef.current[dataIndex].focus(), 10);
    }
  },
  render: (text, record) =>
    filteredInfo?.[dataIndex] ? (
      <Highlighter
        highlightStyle={{ backgroundColor: '#ffc069', padding: 0 }}
        searchWords={[filteredInfo[dataIndex][0]]}
        autoEscape
        textToHighlight={text ? text.toString() : ''}
      />
    ) : (
      text
    ),
});

/**
 * Get numeric filter props for table columns
 * @param {string} dataIndex - Column data index
 * @param {Object} searchInputRef - Ref object for input elements
 * @param {Object} filteredInfo - Current filter state
 * @param {string} placeholder - Input placeholder text
 * @param {Function} handleSearch - Search handler
 * @param {Function} handleReset - Reset handler
 * @returns {Object} - Column props for Ant Design Table
 */
export const getNumericFilterProps = (dataIndex, searchInputRef, filteredInfo, placeholder, handleSearch, handleReset) => ({
  filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
    <div style={{ padding: 8 }}>
      <Input
        type="number"
        ref={node => {
          if (node) {
            searchInputRef.current[dataIndex] = node;
            // Focus input when dropdown opens
            setTimeout(() => node.focus(), 10);
          }
        }}
        placeholder={placeholder || `Search ${dataIndex}`}
        value={selectedKeys[0]}
        onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
        onPressEnter={() => handleSearch(selectedKeys, confirm, dataIndex)}
        style={{ width: 188, marginBottom: 8, display: 'block' }}
      />
      <Space>
        <Button
          type="primary"
          onClick={() => handleSearch(selectedKeys, confirm, dataIndex)}
          icon={<SearchOutlined />}
          size="small"
          style={{ width: 90 }}
        >
          Search
        </Button>
        <Button 
          onClick={() => handleReset(clearFilters, dataIndex)}
          size="small"
          style={{ width: 90 }}
        >
          Reset
        </Button>
      </Space>
    </div>
  ),
  filterIcon: filtered => (
    <SearchOutlined style={{ color: filtered ? '#1890ff' : undefined }} />
  ),
  filteredValue: filteredInfo?.[dataIndex] || null,
  onFilter: (value, record) => {
    if (!record[dataIndex] && record[dataIndex] !== 0) return false;
    
    const recordValue = parseInt(record[dataIndex], 10);
    const filterValue = parseInt(value, 10);
    
    if (isNaN(recordValue) || isNaN(filterValue)) return false;
    
    return recordValue === filterValue;
  },
  onFilterDropdownVisibleChange: visible => {
    if (visible && searchInputRef.current[dataIndex]) {
      setTimeout(() => searchInputRef.current[dataIndex].focus(), 10);
    }
  },
});

/**
 * Get range numeric filter props for table columns (for filtering by ranges)
 * @param {string} dataIndex - Column data index
 * @param {Object} searchInputRef - Ref object for input elements
 * @param {Object} filteredInfo - Current filter state
 * @param {string} placeholder - Input placeholder text
 * @param {Function} handleSearch - Search handler
 * @param {Function} handleReset - Reset handler
 * @returns {Object} - Column props for Ant Design Table
 */
export const getNumericRangeFilterProps = (dataIndex, searchInputRef, filteredInfo, handleSearch, handleReset) => ({
  filters: [
    { text: 'Less than 10', value: 'lt10' },
    { text: '10 to 50', value: '10to50' },
    { text: 'More than 50', value: 'gt50' },
  ],
  filteredValue: filteredInfo?.[dataIndex] || null,
  onFilter: (value, record) => {
    const num = parseInt(record[dataIndex], 10);
    if (isNaN(num)) return false;
    
    if (value === 'lt10') return num < 10;
    if (value === '10to50') return num >= 10 && num <= 50;
    if (value === 'gt50') return num > 50;
    
    return true;
  },
  filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
    <div style={{ padding: 8 }}>
      <Input
        type="number"
        ref={node => {
          if (node) {
            searchInputRef.current[dataIndex] = node;
            // Focus input when dropdown opens
            setTimeout(() => node.focus(), 10);
          }
        }}
        placeholder={`Search exact ${dataIndex}`}
        value={selectedKeys[0]}
        onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
        onPressEnter={() => handleSearch(selectedKeys, confirm, dataIndex)}
        style={{ width: 188, marginBottom: 8, display: 'block' }}
      />
      <Space>
        <Button
          type="primary"
          onClick={() => handleSearch(selectedKeys, confirm, dataIndex)}
          icon={<SearchOutlined />}
          size="small"
          style={{ width: 90 }}
        >
          Search
        </Button>
        <Button 
          onClick={() => handleReset(clearFilters, dataIndex)}
          size="small"
          style={{ width: 90 }}
        >
          Reset
        </Button>
      </Space>
    </div>
  ),
  onFilterDropdownVisibleChange: visible => {
    if (visible && searchInputRef.current[dataIndex]) {
      setTimeout(() => searchInputRef.current[dataIndex].focus(), 10);
    }
  },
});

// Enhanced standard columns for card tables
export const getStandardTableColumns = (onCardClick, searchInputRef, filteredInfo, handleSearch, handleReset) => [
  {
    title: 'Card Name',
    dataIndex: 'name',
    key: 'name',
    render: (text, record) => (
      <span
        onClick={(e) => {
          e.stopPropagation();
          onCardClick(record);
        }}
        style={cardNameStyle}
      >
        {text}
      </span>
    ),
    sorter: (a, b) => a.name.localeCompare(b.name),
    ...getColumnSearchProps('name', searchInputRef, filteredInfo, 'Search card name', handleSearch, handleReset),
  },
  {
    title: 'Set',
    dataIndex: 'set_name',
    key: 'set_name',
    sorter: (a, b) => (a.set_name || '').localeCompare(b.set_name || ''),
    ...getColumnSearchProps('set_name', searchInputRef, filteredInfo, 'Search set name', handleSearch, handleReset),
  },
  {
    title: 'Price',
    dataIndex: 'price',
    key: 'price',
    render: (price) => price ? `$${price.toFixed(2)}` : '-',
    sorter: (a, b) => (parseFloat(a.price) || 0) - (parseFloat(b.price) || 0),
    ...getNumericFilterProps('price', searchInputRef, filteredInfo, 'Search price', handleSearch, handleReset),
  },
  {
    title: 'Quality',
    dataIndex: 'quality',
    key: 'quality',
    sorter: (a, b) => (a.quality || '').localeCompare(b.quality || ''),
    filters: [
      { text: 'NM', value: 'NM' },
      { text: 'LP', value: 'LP' },
      { text: 'MP', value: 'MP' },
      { text: 'HP', value: 'HP' },
    ],
    filteredValue: filteredInfo?.quality || null,
    onFilter: (value, record) => record.quality === value,
  },
  {
    title: 'Quantity',
    dataIndex: 'quantity',
    key: 'quantity',
    sorter: (a, b) => parseInt(a.quantity || 0, 10) - parseInt(b.quantity || 0, 10),
    ...getNumericFilterProps('quantity', searchInputRef, filteredInfo, 'Search quantity', handleSearch, handleReset),
  },
  {
    title: 'Language',
    dataIndex: 'language',
    key: 'language',
    sorter: (a, b) => (a.language || '').localeCompare(b.language || ''),
    filters: [
      { text: 'English', value: 'English' },
      { text: 'Japanese', value: 'Japanese' },
      { text: 'German', value: 'German' },
      { text: 'French', value: 'French' },
    ],
    filteredValue: filteredInfo?.language || null,
    onFilter: (value, record) => record.language === value,
  }
];

// New utility for handling table changes consistently
export const handleTableChangeUtil = (pagination, filters, sorter, setFilteredInfo, setSortedInfo, setPagination) => {
  setFilteredInfo(filters);
  setSortedInfo(sorter);
  if (setPagination) {
    setPagination(pagination);
  }
};

// New utility for creating a checkbox column for selection
export const getCheckboxColumn = (selectedIds, handleCheckboxChange, selectAllChecked, handleSelectAll) => ({
  title: (
    <input
      type="checkbox"
      checked={selectAllChecked}
      onChange={(e) => handleSelectAll(e)}
    />
  ),
  dataIndex: 'checkbox',
  key: 'checkbox',
  align: 'center',
  width: '50px',
  render: (_, record) => (
    <input
      type="checkbox"
      checked={selectedIds.has(record.id)}
      onChange={(e) => handleCheckboxChange(record.id, e)}
      onClick={(e) => e.stopPropagation()}
    />
  ),
});

// New utility for creating a common pagination config
export const getStandardPagination = (customConfig = {}) => ({
  pageSize: 10,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100'],
  showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} items`,
  ...customConfig
});

export { cardNameStyle };