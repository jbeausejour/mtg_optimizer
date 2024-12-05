
import React from 'react';
import { Card } from 'antd';
import ScryfallCard from '../CardManagement/ScryfallCard';

const ScryfallCardView = ({ cardData, mode = 'view', onPrintingSelect, onSetClick }) => {
  return (
    <Card>
      <ScryfallCard 
        data={cardData}
        isEditable={mode === 'edit'}
        onPrintingSelect={mode === 'edit' ? onPrintingSelect : undefined}
        onSetClick={mode === 'edit' ? onSetClick : undefined}
      />
    </Card>
  );
};

export default ScryfallCardView;