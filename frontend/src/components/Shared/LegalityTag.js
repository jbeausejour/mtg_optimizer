// frontend/src/components/Shared/LegalityTag.js
import React from 'react';
import { Tag } from 'antd';

const color = {
  legal: 'green',
  not_legal: 'lightgray',
  banned: 'red',
  restricted: 'blue'
};

const LegalityTag = ({ format, legality }) => {

  return (
    <Tag color={color[legality]}>
      {format}
    </Tag>
  );
};

export default LegalityTag;
