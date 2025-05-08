// frontend/src/components/Shared/ManaSymbol.js
import React from 'react';

const ManaSymbol = ({ symbol }) => (
  <img 
    src={`https://svgs.scryfall.io/card-symbols/${symbol.replace(/[{}]/g, '').toUpperCase()}.svg`} 
    alt={symbol} 
    style={{ height: 16, marginLeft: 4 }} 
  />
);

export default ManaSymbol;
