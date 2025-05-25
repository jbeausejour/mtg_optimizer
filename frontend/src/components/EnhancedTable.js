import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Table, Checkbox, Space } from 'antd';
import { ExportOptions } from '../utils/exportUtils';
import { getStandardPagination } from '../utils/tableConfig';

/**
 * Higher-Order Table Component that wraps Ant Design's Table
 * with consistent functionality for filtering, sorting, selection,
 * and state persistence
 */
const EnhancedTable = ({
  dataSource = [],
  columns = [],
  enableExport = true,
  exportFilename = 'export', 
  exportCopyFormat = "cardlist", 
  onRowClick,
  rowSelectionEnabled = false,
  persistStateKey = null,
  defaultSortInfo = {},
  defaultFilteredInfo = {},
  defaultPagination = {},
  selectedIds,
  onSelectionChange,
  showSelectionCount = true,
  onChange,
  ...otherProps
}) => {
  // State management for filtering, sorting, pagination
  const [filteredInfo, setFilteredInfo] = useState(defaultFilteredInfo);
  const [sortedInfo, setSortedInfo] = useState(defaultSortInfo);
  const [pagination, setPagination] = useState(getStandardPagination(defaultPagination));
  const [selectAllChecked, setSelectAllChecked] = useState(false);
  
  // Reference to search inputs
  const searchInput = useRef({});

  // Load persisted state if a key is provided
  useEffect(() => {
    if (persistStateKey) {
      const savedState = loadTableState(persistStateKey);
      if (savedState) {
        setFilteredInfo(savedState.filteredInfo || {});
        setSortedInfo(savedState.sortedInfo || {});
        setPagination(prev => ({
          ...getStandardPagination(),
          ...prev,
          ...savedState.pagination
        }));
      }
    }
  }, [persistStateKey]);

  // Save state when it changes
  useEffect(() => {
    if (persistStateKey) {
      saveTableState(persistStateKey, {
        filteredInfo,
        sortedInfo,
        pagination
      });
    }
  }, [filteredInfo, sortedInfo, pagination, persistStateKey]);

  // Get the filtered data based on current filters
  const getFilteredData = useCallback(() => {
    if (!filteredInfo || Object.keys(filteredInfo).length === 0) {
      return dataSource;
    }

    let filtered = [...dataSource];
    
    // Apply each filter
    Object.keys(filteredInfo).forEach(key => {
      const filterValues = filteredInfo[key];
      if (filterValues && filterValues.length > 0) {
        // Find matching column
        const column = columns.find(col => col.dataIndex === key || col.key === key);
        if (column && column.onFilter) {
          // Apply each filter value using OR logic
          filtered = filtered.filter(record => {
            return filterValues.some(value => column.onFilter(value, record));
          });
        }
      }
    });
    
    return filtered;
  }, [dataSource, filteredInfo, columns]);

  // Update selectAllChecked state based on current selection and filtered data
  useEffect(() => {
    if (!rowSelectionEnabled || !selectedIds) return;
    
    const filteredData = getFilteredData();
    const allSelected = filteredData.length > 0 && 
                        filteredData.every(item => selectedIds.has(item.id));
    setSelectAllChecked(allSelected);
  }, [selectedIds, getFilteredData, rowSelectionEnabled]);

  // Handle table change events (sorting, filtering, pagination)
  const handleTableChange = (paginationConfig, filters, sorter) => {
    setFilteredInfo(filters);
    setSortedInfo(Array.isArray(sorter) ? sorter[0] : sorter); // Handle multi-sort case
    setPagination(paginationConfig);
    
    // Pass changes to parent component
    if (onChange) {
      onChange(paginationConfig, filters, sorter);
    }
  };

  // Handle checkbox selection for individual rows
  const handleCheckboxChange = (recordId, e) => {
    if (e) e.stopPropagation();
    if (!onSelectionChange || !selectedIds) return;
    
    const newSelection = new Set(selectedIds);
    if (newSelection.has(recordId)) {
      newSelection.delete(recordId);
    } else {
      newSelection.add(recordId);
    }
    
    // Update parent component with new selection
    onSelectionChange(newSelection);
  };

  // Handle select all checkbox
  const handleSelectAll = (e) => {
    if (e) e.stopPropagation();
    if (!onSelectionChange || !selectedIds) return;
    
    // Get current filtered data for selection
    const filteredData = getFilteredData();
    const visibleIds = filteredData.map(item => item.id);
    
    let newSelection;
    if (selectAllChecked) {
      // Deselect all filtered items
      newSelection = new Set(selectedIds);
      visibleIds.forEach(id => newSelection.delete(id));
    } else {
      // Select all filtered items
      newSelection = new Set(selectedIds);
      visibleIds.forEach(id => newSelection.add(id));
    }
    
    // Update parent component with new selection
    onSelectionChange(newSelection);
  };

  // Add checkbox column if selection is enabled
  const enhancedColumns = rowSelectionEnabled && selectedIds
    ? [
        {
          title: (
            <div onClick={e => e.stopPropagation()}>
              <Checkbox
                checked={selectAllChecked}
                onChange={handleSelectAll}
              />
              {showSelectionCount && selectedIds.size > 0 && (
                <span style={{ marginLeft: '5px', fontSize: '12px' }}>
                  ({selectedIds.size})
                </span>
              )}
            </div>
          ),
          dataIndex: 'checkbox',
          key: 'checkbox',
          align: 'center',
          width: '60px',
          render: (_, record) => (
            <Checkbox
              checked={selectedIds.has(record.id)}
              onChange={(e) => handleCheckboxChange(record.id, e)}
              onClick={(e) => e.stopPropagation()}
            />
          ),
        },
        ...columns
      ] 
    : columns;

  // Configure onRow handler for row clicking
  const onRowConfig = record => ({
    onClick: (event) => {
      // Don't trigger row click when clicking on a checkbox or button
      if (!event.target.closest('.ant-checkbox-wrapper') && 
          !event.target.closest('button') && 
          onRowClick) {
        onRowClick(record);
      }
    },
    style: { cursor: onRowClick ? 'pointer' : 'default' }
  });

  // Enhanced pagination configuration
  const paginationConfig = {
    ...pagination,
    onChange: (page, pageSize) => {
      setPagination(prev => ({
        ...prev,
        current: page,
        pageSize
      }));
    }
  };

  return (
    <>
      {enableExport && (
        <div style={{ marginBottom: 12 }}>
          <ExportOptions
            dataSource={getFilteredData()}
            columns={columns}
            filename={exportFilename}
            copyFormat={exportCopyFormat}
          />
        </div>
      )}
      <Table
        dataSource={dataSource}
        columns={enhancedColumns}
        rowKey="id"
        onChange={handleTableChange}
        pagination={paginationConfig}
        onRow={onRowConfig}
        {...otherProps}
      />
      </>
    );
  };

// Utility function to save table state to localStorage
const saveTableState = (tableId, state) => {
  try {
    localStorage.setItem(`table_state_${tableId}`, JSON.stringify(state));
  } catch (error) {
    console.error('Error saving table state:', error);
  }
};

// Utility function to load table state from localStorage
const loadTableState = (tableId) => {
  try {
    const savedState = localStorage.getItem(`table_state_${tableId}`);
    return savedState ? JSON.parse(savedState) : null;
  } catch (error) {
    console.error('Error loading table state:', error);
    return null;
  }
};

export default EnhancedTable;