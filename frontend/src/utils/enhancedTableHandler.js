import { useState, useRef, useCallback, useEffect } from 'react';
import { useSettings } from './SettingsContext';
import { getStandardPagination } from './tableConfig';

/**
 * Utility function to create consistent table state and handlers
 * for use across all table components.
 * 
 * @param {Object} initialConfig - Initial configuration
 * @param {String} persistKey - Key for localStorage persistence
 * @returns {Object} Unified table state and handlers
 */
export const useEnhancedTableHandler = (initialConfig = {}, persistKey = null) => {
  const { settings } = useSettings();
  // Initialize state with either persisted state, provided initialConfig, or defaults
  const [filteredInfo, setFilteredInfo] = useState(initialConfig.filteredInfo || {});
  const [sortedInfo, setSortedInfo] = useState(initialConfig.sortedInfo || {});
  const [pagination, setPagination] = useState(
    initialConfig.pagination || getStandardPagination()
  );
  const [selectedIds, setSelectedIds] = useState(new Set(initialConfig.selectedIds || []));
  const [selectAllChecked, setSelectAllChecked] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState(initialConfig.visibleColumns || []);
  const searchInput = useRef({});

  // Update pagination when settings change
  useEffect(() => {
    setPagination(prev => ({
      ...prev,
      pageSize: settings.itemsPerPage || 20,
      current: 1 // Reset to first page when page size changes
    }));
  }, [settings.itemsPerPage]);

  // Load persisted state if a key is provided
  useEffect(() => {
    if (persistKey) {
      try {
        const savedState = localStorage.getItem(`table_state_${persistKey}`);
        if (savedState) {
          const parsedState = JSON.parse(savedState);
          setFilteredInfo(parsedState.filteredInfo || {});
          setSortedInfo(parsedState.sortedInfo || {});
          const savedPagination = parsedState.pagination || {};
          setPagination(prev => ({
            ...getStandardPagination(settings.itemsPerPage),
            ...prev,
            ...savedPagination,
            pageSize: settings.itemsPerPage || savedPagination.pageSize || 20
          }));
          
          if (parsedState.selectedIds) {
            setSelectedIds(new Set(parsedState.selectedIds));
          }
          
          if (parsedState.visibleColumns) {
            setVisibleColumns(parsedState.visibleColumns);
          }
        }
      } catch (error) {
        console.error('Error loading table state:', error);
      }
    }
  }, [persistKey]);

  // Save state when it changes
  useEffect(() => {
    if (persistKey) {
      try {
        localStorage.setItem(`table_state_${persistKey}`, JSON.stringify({
          filteredInfo,
          sortedInfo,
          pagination,
          selectedIds: Array.from(selectedIds),
          visibleColumns
        }));
      } catch (error) {
        console.error('Error saving table state:', error);
      }
    }
  }, [filteredInfo, sortedInfo, pagination, selectedIds, visibleColumns, persistKey]);

  // Handle table change events (sorting, filtering, pagination)
  const handleTableChange = useCallback((paginationConfig, filters, sorter) => {
    setFilteredInfo(filters);
    setSortedInfo(Array.isArray(sorter) ? sorter[0] : sorter); // Handle multi-sort case
    setPagination(paginationConfig);
  }, []);

  // Handle search in filter dropdowns
  const handleSearch = useCallback((selectedKeys, confirm, dataIndex) => {
    confirm();
    setFilteredInfo(prev => ({
      ...prev,
      [dataIndex]: selectedKeys
    }));
  }, []);

  // Reset a specific filter
  const handleReset = useCallback((clearFilters, dataIndex) => {
    clearFilters();
    setFilteredInfo(prev => {
      const newFilteredInfo = { ...prev };
      delete newFilteredInfo[dataIndex];
      return newFilteredInfo;
    });
  }, []);

  // Reset all filters, sorting, and search inputs
  const handleResetAllFilters = useCallback(() => {
    setFilteredInfo({});
    setSortedInfo({});
    if (searchInput.current) {
      Object.keys(searchInput.current).forEach(key => {
        if (searchInput.current[key]) {
          // Clear input values if they're controlled
          if (searchInput.current[key].value !== undefined) {
            searchInput.current[key].value = '';
          }
        }
      });
    }
  }, []);

  /**
   * Apply filters to a dataset to get currently visible records
   * @param {Array} dataSource - The full dataset
   * @param {Array} columns - Table column definitions with filter handlers
   * @returns {Array} Filtered dataset
   */
  const getFilteredData = useCallback((dataSource, columns) => {
    if (!dataSource || !columns || !filteredInfo || Object.keys(filteredInfo).length === 0) {
      return dataSource || [];
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
  }, [filteredInfo]);

  // Handle row selection via checkbox
  const handleCheckboxChange = useCallback((recordId, e, dataSource, columns) => {
    if (e) e.stopPropagation();
    
    setSelectedIds(prev => {
      const newSelection = new Set(prev);
      if (newSelection.has(recordId)) {
        newSelection.delete(recordId);
      } else {
        newSelection.add(recordId);
      }
      
      // Update "select all" state based on filtered data
      if (dataSource && columns) {
        const filteredData = getFilteredData(dataSource, columns);
        const allFilteredSelected = filteredData.length > 0 && 
                                   filteredData.every(item => newSelection.has(item.id));
        setSelectAllChecked(allFilteredSelected);
      }
      
      return newSelection;
    });
  }, [getFilteredData]);

  // Handle "select all" checkbox
  const handleSelectAll = useCallback((e, dataSource, columns) => {
    if (e) e.stopPropagation();
    
    if (!dataSource) {
      return;
    }
    
    // Get currently filtered data
    const filteredData = getFilteredData(dataSource, columns);
    const filteredIds = filteredData.map(item => item.id);
    
    if (selectAllChecked) {
      // Deselect only the filtered items
      setSelectedIds(prev => {
        const newSelection = new Set(prev);
        filteredIds.forEach(id => newSelection.delete(id));
        return newSelection;
      });
    } else {
      // Select all filtered items
      setSelectedIds(prev => {
        const newSelection = new Set(prev);
        filteredIds.forEach(id => newSelection.add(id));
        return newSelection;
      });
    }
    
    setSelectAllChecked(!selectAllChecked);
  }, [selectAllChecked, getFilteredData]);

  // Handle bulk deletion
  const handleBulkDelete = useCallback((deleteFunction, confirmMessage = 'Are you sure you want to delete selected items?') => {
    if (!deleteFunction || selectedIds.size === 0) {
      return;
    }
    
    // Implementation is left to the component since it depends on API calls
  }, [selectedIds]);

  // Update selectAllChecked based on current selection and filtered data
  const updateSelectAllState = useCallback((dataSource, columns) => {
    if (!dataSource || !columns) return;
    
    const filteredData = getFilteredData(dataSource, columns);
    const allFilteredSelected = filteredData.length > 0 && 
                               filteredData.every(item => selectedIds.has(item.id));
    setSelectAllChecked(allFilteredSelected);
  }, [selectedIds, getFilteredData]);

  // Reset selection state
  const resetSelection = useCallback(() => {
    setSelectedIds(new Set());
    setSelectAllChecked(false);
  }, []);

  // Handle column visibility changes
  const handleColumnVisibilityChange = useCallback((newVisibleColumns) => {
    setVisibleColumns(newVisibleColumns);
  }, []);

  return {
    
    // State
    filteredInfo,
    sortedInfo,
    pagination,
    selectedIds,
    selectAllChecked,
    searchInput,
    visibleColumns,
    
    // Setters
    setFilteredInfo,
    setSortedInfo,
    setPagination,
    setSelectedIds,
    setSelectAllChecked,
    setVisibleColumns,
    
    // Handlers
    handleTableChange,
    handleSearch,
    handleReset,
    handleResetAllFilters,
    handleCheckboxChange,
    handleSelectAll,
    handleBulkDelete,
    resetSelection,
    handleColumnVisibilityChange,
    
    // Utilities
    getFilteredData,
    updateSelectAllState
  };
};

export default useEnhancedTableHandler;