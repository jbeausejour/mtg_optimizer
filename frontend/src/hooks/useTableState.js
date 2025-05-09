import { useState, useRef, useCallback, useEffect } from 'react';
import { getStandardPagination } from '../utils/tableConfig';

/**
 * Enhanced hook for managing table state including filtering, sorting, pagination, and selection
 * with proper handling of filtered data for selection
 * 
 * @param {Object} initialConfig - Initial configuration for the table state
 * @param {string} persistKey - Key to use for state persistence in localStorage
 * @returns {Object} Table state and handler functions
 */
const useTableState = (initialConfig = {}, persistKey = null) => {
  // Initialize state with either persisted state, provided initialConfig, or defaults
  const [filteredInfo, setFilteredInfo] = useState(initialConfig.filteredInfo || {});
  const [sortedInfo, setSortedInfo] = useState(initialConfig.sortedInfo || {});
  const [pagination, setPagination] = useState(
    initialConfig.pagination || getStandardPagination()
  );
  const [selectedIds, setSelectedIds] = useState(new Set(initialConfig.selectedIds || []));
  const [selectAllChecked, setSelectAllChecked] = useState(false);
  const searchInput = useRef({});

  // Load persisted state if a key is provided
  useEffect(() => {
    if (persistKey) {
      const savedState = loadTableState(persistKey);
      if (savedState) {
        setFilteredInfo(savedState.filteredInfo || {});
        setSortedInfo(savedState.sortedInfo || {});
        setPagination(prev => ({
          ...getStandardPagination(),
          ...prev,
          ...savedState.pagination
        }));
        setSelectedIds(new Set(savedState.selectedIds || []));
      }
    }
  }, [persistKey]);

  // Save state when it changes
  useEffect(() => {
    if (persistKey) {
      saveTableState(persistKey, {
        filteredInfo,
        sortedInfo,
        pagination,
        selectedIds: Array.from(selectedIds)
      });
    }
  }, [filteredInfo, sortedInfo, pagination, selectedIds, persistKey]);

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
          searchInput.current[key].value = '';
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

  // Update selectAllChecked based on current selection and filtered data
  const updateSelectAllState = useCallback((dataSource, columns) => {
    if (!dataSource || !columns) return;
    
    const filteredData = getFilteredData(dataSource, columns);
    const allFilteredSelected = filteredData.length > 0 && 
                               filteredData.every(item => selectedIds.has(item.id));
    setSelectAllChecked(allFilteredSelected);
  }, [selectedIds, getFilteredData]);

  // Reset selection state when data changes
  const resetSelection = useCallback(() => {
    setSelectedIds(new Set());
    setSelectAllChecked(false);
  }, []);

  return {
    // State
    filteredInfo,
    sortedInfo,
    pagination,
    selectedIds,
    selectAllChecked,
    searchInput,
    
    // Setters
    setFilteredInfo,
    setSortedInfo,
    setPagination,
    setSelectedIds,
    setSelectAllChecked,
    
    // Handlers
    handleTableChange,
    handleSearch,
    handleReset,
    handleResetAllFilters,
    handleCheckboxChange,
    handleSelectAll,
    resetSelection,
    
    // Utilities
    getFilteredData,
    updateSelectAllState
  };
};

export default useTableState;