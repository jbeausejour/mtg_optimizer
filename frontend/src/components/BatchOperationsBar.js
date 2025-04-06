import React from 'react';
import { Button, Space, Card, Typography } from 'antd';

const { Text } = Typography;

/**
 * Component for displaying batch operations for selected items
 * 
 * @param {Object} props
 * @param {Set} props.selectedIds - Set of selected item IDs
 * @param {Array} props.operations - Array of operation objects with {key, label, icon, action, danger}
 * @param {Function} props.getSelectedItems - Function to get items from IDs (optional)
 * @param {string} props.title - Title for the batch operations bar (optional)
 */
const BatchOperationsBar = ({ 
  selectedIds, 
  operations = [],
  getSelectedItems,
  title = "Batch Operations" 
}) => {
  if (!selectedIds || selectedIds.size === 0) {
    return null;
  }

  return (
    <Card 
      style={{ 
        marginBottom: 16,
        background: '#f5f5f5',
        border: '1px dashed #d9d9d9'
      }}
    >
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <Text strong>{title} ({selectedIds.size} selected)</Text>
        
        <Space>
          {operations.map(op => (
            <Button
              key={op.key}
              type={op.danger ? "primary" : "default"}
              danger={op.danger}
              icon={op.icon}
              onClick={() => op.action(
                getSelectedItems ? getSelectedItems(Array.from(selectedIds)) : Array.from(selectedIds)
              )}
            >
              {op.label}
            </Button>
          ))}
        </Space>
      </div>
    </Card>
  );
};

export default BatchOperationsBar;