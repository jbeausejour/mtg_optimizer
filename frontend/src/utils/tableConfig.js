import React, { useRef, useEffect, useState } from 'react';
import { Button } from 'antd';
import { SearchOutlined } from '@ant-design/icons';

// Style for card name links
const cardNameStyle = {
  color: 'inherit',
  cursor: 'pointer',
  textDecoration: 'none',
  borderBottom: '1px dotted #999',
};

// Reusable filter dropdown component that works for any column
const FilterDropdown = (props) => {
  const { setSelectedKeys, selectedKeys, confirm, clearFilters, dataIndex, placeholder } = props;
  const searchInput = useRef(null);
  
  // Setup a ref to track when the component has been mounted
  const hasRendered = useRef(false);

  useEffect(() => {
    // Focus the input on each render, not just the first
    // This ensures focus works when reopening the dropdown
    const focusInput = () => {
      if (searchInput.current) {
        searchInput.current.focus();
      }
    };
    
    // Small delay to ensure DOM is ready
    const timer = setTimeout(focusInput, 10);
    return () => clearTimeout(timer);
  });

  return (
    <div style={{ padding: 8 }}>
      <input
        ref={searchInput}
        placeholder={placeholder || `Search ${dataIndex}`}
        value={selectedKeys[0] || ''}
        onChange={(e) => setSelectedKeys(e.target.value ? [e.target.value] : [])}
        onKeyDown={(e) => e.key === 'Enter' && confirm()}
        style={{ width: 188, marginBottom: 8, display: 'block' }}
        autoFocus={true}
      />
      <Button
        type="primary"
        onClick={() => confirm()}
        icon={<SearchOutlined />}
        size="small"
        style={{ width: 90, marginRight: 8 }}
      >
        Search
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
  );
};

// Generic column search props generator
export const getColumnSearchProps = (dataIndex, searchInput, filteredInfo, placeholder) => ({
  filterDropdown: (props) => (
    <FilterDropdown 
      {...props} 
      dataIndex={dataIndex} 
      placeholder={placeholder}
    />
  ),
  filterIcon: (filtered) => (
    <SearchOutlined style={{ color: filtered ? '#1890ff' : undefined }} />
  ),
  filteredValue: filteredInfo?.[dataIndex] || null,
  onFilter: (value, record) => 
    record[dataIndex]
      ? record[dataIndex].toString().toLowerCase().includes(value.toLowerCase())
      : '',
  // Use onFilterDropdownVisibleChange to ensure focus is set when dropdown opens
  onFilterDropdownOpenChange: (visible) => {
    if (visible) {
      // setTimeout ensures this runs after the dropdown has fully rendered
      setTimeout(() => {
        if (document.querySelector('.ant-table-filter-dropdown input')) {
          document.querySelector('.ant-table-filter-dropdown input').focus();
        }
      }, 100);
    }
  }
});

// Card-specific columns with filtering capabilities
export const getStandardTableColumns = (onCardClick, searchInput, filteredInfo, handleSearch, handleReset) => [
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
    ...getColumnSearchProps('name', searchInput, filteredInfo, 'Search card name'),
  },
  {
    title: 'Set',
    dataIndex: 'set_name',
    key: 'set_name',
    sorter: (a, b) => a.set_name?.localeCompare(b.set_name),
    ...getColumnSearchProps('set_name', searchInput, filteredInfo, 'Search set name'),
  },
  {
    title: 'Price',
    dataIndex: 'price',
    key: 'price',
    render: (price) => price ? `$${price.toFixed(2)}` : '-',
    sorter: (a, b) => (a.price || 0) - (b.price || 0),
  },
  {
    title: 'Quality',
    dataIndex: 'quality',
    key: 'quality',
    sorter: (a, b) => a.quality?.localeCompare(b.quality),
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
    sorter: (a, b) => (a.quantity || 0) - (b.quantity || 0),
  },
  {
    title: 'Language',
    dataIndex: 'language',
    key: 'language',
    sorter: (a, b) => a.language?.localeCompare(b.language),
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

export { cardNameStyle };