import React, { useState, useEffect } from 'react';
import { Button, Dropdown, Checkbox, Space, Typography } from 'antd';
import { SettingOutlined } from '@ant-design/icons';

const { Text } = Typography;

/**
 * Component for selecting which columns to display in a table
 * 
 * @param {Object} props
 * @param {Array} props.columns - Array of column objects
 * @param {Array} props.visibleColumns - Array of visible column keys
 * @param {Function} props.onColumnToggle - Function to call when columns change
 * @param {string} props.persistKey - Key for persisting column selection in localStorage
 */
const ColumnSelector = ({ 
  columns = [], 
  visibleColumns = [], 
  onColumnToggle, 
  persistKey 
}) => {
  const [selectedColumns, setSelectedColumns] = useState(visibleColumns);

  // Load persisted column selection on mount
  useEffect(() => {
    if (persistKey) {
      try {
        const savedColumns = localStorage.getItem(persistKey);
        if (savedColumns) {
          const parsedColumns = JSON.parse(savedColumns);
          if (Array.isArray(parsedColumns) && parsedColumns.length > 0) {
            setSelectedColumns(parsedColumns);
            if (onColumnToggle) {
              onColumnToggle(parsedColumns);
            }
          }
        }
      } catch (error) {
        console.error('Error loading column selection:', error);
      }
    }
  }, [persistKey, onColumnToggle]);

  // Save column selection when it changes
  useEffect(() => {
    if (persistKey && selectedColumns.length > 0) {
      try {
        localStorage.setItem(persistKey, JSON.stringify(selectedColumns));
      } catch (error) {
        console.error('Error saving column selection:', error);
      }
    }
  }, [selectedColumns, persistKey]);

  // Handle column toggle
  const handleColumnToggle = (columnKey) => {
    const newSelection = selectedColumns.includes(columnKey)
      ? selectedColumns.filter(key => key !== columnKey)
      : [...selectedColumns, columnKey];
    
    setSelectedColumns(newSelection);
    
    if (onColumnToggle) {
      onColumnToggle(newSelection);
    }
  };

  // Check if a column can be toggled (prevent toggling all columns off)
  const canToggleColumn = (columnKey) => {
    // If this is the last visible column, don't allow toggling off
    return !(selectedColumns.length === 1 && selectedColumns.includes(columnKey));
  };

  // Reset to default columns (all visible)
  const resetToDefault = () => {
    const defaultColumns = columns.map(col => col.key || col.dataIndex);
    setSelectedColumns(defaultColumns);
    
    if (onColumnToggle) {
      onColumnToggle(defaultColumns);
    }
  };

  // Skip rendering if no columns
  if (!columns || columns.length === 0) {
    return null;
  }

  // Create dropdown menu items
  const items = [
    {
      key: 'reset',
      label: <Button type="link" onClick={resetToDefault}>Reset to Default</Button>
    },
    {
      key: 'divider',
      type: 'divider',
    },
    ...columns
      .filter(col => col.key || col.dataIndex) // Only include columns with keys
      .map(column => {
        const columnKey = column.key || column.dataIndex;
        return {
          key: columnKey,
          label: (
            <Checkbox
              checked={selectedColumns.includes(columnKey)}
              onChange={() => handleColumnToggle(columnKey)}
              disabled={!canToggleColumn(columnKey)}
            >
              {column.title || columnKey}
            </Checkbox>
          )
        };
      })
  ];
  
  return (
    <Dropdown
      menu={{ items }}
      trigger={['click']}
      placement="bottomLeft"
    >
      <Button icon={<SettingOutlined />}>
        Columns
      </Button>
    </Dropdown>
  );
};

export default ColumnSelector;