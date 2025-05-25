import React from 'react';
import { Button, Dropdown, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';
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
export const exportToExcel = (dataSource, columns, filename = 'export.xlsx') => {
  const headers = columns.map(col => col.title || col.dataIndex);
  const keys = columns.map(col => col.dataIndex);

  const data = dataSource.map(row =>
    keys.map(key => row[key] !== undefined ? row[key] : '')
  );

  const worksheetData = [headers, ...data];
  const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Sheet1');

  const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
  const blob = new Blob([excelBuffer], { type: 'application/octet-stream' });
  saveAs(blob, filename);
};

export const ExportOptions = ({ dataSource, columns, filename = 'export', copyFormat = 'cardlist' }) => {
  const handleExportCSV = () => {
    exportToCSV(dataSource, columns, `${filename}.csv`);
  };

  const handleExportExcel = () => {
    exportToExcel(dataSource, columns, `${filename}.xlsx`);
  };

  const handleCopyToClipboard = () => {
    let text = '';

    if (copyFormat === 'cardlist') {
      text = dataSource
        .filter(row => row.name)
        .map(row => `${row.quantity || 1} ${row.name}`)
        .join('\n');
    }

    if (!text) {
      message.warning('Nothing to copy or unsupported format.');
      return;
    }

    navigator.clipboard.writeText(text)
      .then(() => message.success('Copied to clipboard!'))
      .catch(() => message.error('Failed to copy.'));
  };

  const menuItems = [
    { key: 'csv', label: 'Export as CSV', onClick: handleExportCSV },
    { key: 'excel', label: 'Export as Excel', onClick: handleExportExcel },
  ];
  
  if (copyFormat === 'cardlist') {
    menuItems.push({ key: 'clipboard', label: 'Copy to Clipboard (qty name)', onClick: handleCopyToClipboard });
  }
  
  return (
    <Dropdown menu={{ items: menuItems }} trigger={['click']}>
      <Button icon={<DownloadOutlined />}>Export</Button>
    </Dropdown>
  );
};
