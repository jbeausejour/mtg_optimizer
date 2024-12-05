import { Button } from 'antd';

const cardNameStyle = {
  color: 'inherit',
  cursor: 'pointer',
  textDecoration: 'none',
  borderBottom: '1px dotted #999',
};

export const getStandardTableColumns = (onCardClick) => [
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
    filterDropdown: ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
      <div style={{ padding: 8 }}>
        <input
          placeholder="Search card name"
          value={selectedKeys[0] || ''}
          onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
          onPressEnter={confirm}
          style={{ width: 188, marginBottom: 8, display: 'block' }}
        />
        <Button onClick={confirm} size="small" style={{ width: 90, marginRight: 8 }}>Filter</Button>
        <Button onClick={clearFilters} size="small" style={{ width: 90 }}>Reset</Button>
      </div>
    ),
    onFilter: (value, record) => record.name?.toLowerCase().includes(value.toLowerCase()),
  },
  {
    title: 'Set',
    dataIndex: 'set_name',
    key: 'set_name',
    sorter: (a, b) => a.set_name?.localeCompare(b.set_name),
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
    onFilter: (value, record) => record.quality === value,
  },
  {
    title: 'Quantity',
    dataIndex: 'quantity',
    key: 'quantity',
    sorter: (a, b) => (a.quantity || 0) - (b.quantity || 0),
  }
];

export { cardNameStyle };