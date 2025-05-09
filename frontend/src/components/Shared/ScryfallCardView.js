import React, { useState, useEffect } from 'react';
import ScryfallCard from '../CardManagement/ScryfallCard';

const ScryfallCardView = ({ cardData, mode, onSave, onChange }) => {
  // console.log("ScryfallCardView Receiving carddata: ", cardData);
  const isEditMode = mode === 'edit';
  const [pendingSelection, setPendingSelection] = useState(() => ({
    id: cardData.id,
    name: cardData.name,
    buylist_id: cardData.buylist_id,
    user_id: cardData.user_id,
    language: cardData.language || 'English',
    quality: cardData.quality || 'NM',
    version: cardData.version || 'Standard',
    foil: cardData.foil || false,
    quantity: cardData.quantity || 1,
    set_code: cardData.set_code || '',
    set_name: cardData.set_name || ''
  }));
  
  useEffect(() => {
    if (isEditMode) {
      setPendingSelection({
        id: cardData.id,
        name: cardData.name,
        buylist_id: cardData.buylist_id,
        user_id: cardData.user_id,
        language: cardData.language || 'English',
        quality: cardData.quality || 'NM',
        version: cardData.version || 'Standard',
        foil: cardData.foil || false,
        quantity: cardData.quantity || 1,
        set_code: cardData.set_code || '',
        set_name: cardData.set_name || ''
      });
    }
  }, [cardData?.id]);

  const handleChange = (partialUpdate) => {
    setPendingSelection((prev) => {
      const merged = { ...prev, ...partialUpdate };
      if (onChange) onChange(merged); // ← propagate to parent
      return merged;
    });
  };

  return (
    <>
    <ScryfallCard
      data={{
        id: cardData?.id,
        name: cardData?.name,
        ...cardData
      }}
      editingFields={pendingSelection}
      isEditable={isEditMode}
      onChange={isEditMode ? handleChange : undefined}
    />  
  </>
  );
};

export default ScryfallCardView;
