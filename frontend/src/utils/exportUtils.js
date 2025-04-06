/**
 * Utility functions for exporting table data in various formats
 */

/**
 * Convert data to CSV format and trigger download
 * 
 * @param {Array} dataSource - Array of data objects
 * @param {Array} columns - Array of column configurations
 * @param {String} filename - Name for the downloaded file
 */
export const exportToCSV = (dataSource, columns, filename = 'export.csv') => {
  if (!dataSource || !dataSource.length || !columns || !columns.length) {
    console.error('Cannot export: Missing data or columns');
    return;
  }

  // Extract column headers (use dataIndex or key as fallback)
  const headers = columns
    .filter(col => col.dataIndex && col.title)
    .map(col => col.title);

  // Extract data fields to export (use dataIndex)
  const dataKeys = columns
    .filter(col => col.dataIndex)
    .map(col => col.dataIndex);

  // Create CSV rows
  const rows = [
    // Header row
    headers.join(','),
    // Data rows
    ...dataSource.map(row => (
      dataKeys
        .map(key => {
          // Handle special cases like objects or arrays
          const value = row[key];
          if (value === null || value === undefined) return '';
          
          // Wrap strings with commas in quotes
          if (typeof value === 'string' && value.includes(',')) {
            return `"${value.replace(/"/g, '""')}"`;
          }
          
          return String(value);
        })
        .join(',')
    ))
  ];

  // Create CSV content
  const csvContent = rows.join('\n');

  // Create and trigger download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  
  // Create download link
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  
  // Trigger download
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

/**
 * Export data in Excel format using client-side generation
 * 
 * @param {Array} dataSource - Array of data objects
 * @param {Array} columns - Array of column configurations
 * @param {String} filename - Name for the downloaded file
 * @param {String} sheetName - Name of the worksheet
 */
export const exportToExcel = (dataSource, columns, filename = 'export.xlsx', sheetName = 'Sheet1') => {
  // This is a simplified version that would need to be implemented with a library like SheetJS
  console.error('Excel export requires additional library implementation');
};

/**
 * Component for export options dropdown
 */
import React from 'react';
import { Button, Dropdown, Menu } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';

export const ExportOptions = ({ dataSource, columns, filename = 'export' }) => {
  const handleExportCSV = () => {
    exportToCSV(dataSource, columns, `${filename}.csv`);
  };
  
  const handleExportExcel = () => {
    exportToExcel(dataSource, columns, `${filename}.xlsx`);
  };
  
  const menu = (
    <Menu>
      <Menu.Item key="csv" onClick={handleExportCSV}>Export as CSV</Menu.Item>
      <Menu.Item key="excel" onClick={handleExportExcel}>Export as Excel</Menu.Item>
    </Menu>
  );
  
  return (
    <Dropdown overlay={menu} trigger={['click']}>
      <Button icon={<DownloadOutlined />}>Export</Button>
    </Dropdown>
  );
};
