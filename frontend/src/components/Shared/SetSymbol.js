// src/components/Shared/SetSymbol.js

import React from 'react';
import { Tooltip } from 'antd';

const SetSymbol = ({ setCode, rarity = 'common', collector_number }) => {
  // Normalize promo sets like 'pbro' → 'bro'
  const baseCode = setCode.toLowerCase();
  if (baseCode === 'plst') return null;
  const normalizedCode = baseCode.startsWith('p') && baseCode.length === 4 ? baseCode.slice(1) : baseCode;

  // Override for Secret Lair Drops
  const symbolUrl =
    normalizedCode === 'sld'
      ? 'https://svgs.scryfall.io/sets/star.svg?1745208000'
      : `https://svgs.scryfall.io/sets/${normalizedCode}.svg`;


  return (
    <Tooltip title={`${setCode.toUpperCase()} #${collector_number} (${rarity})`}>
      <img
        src={symbolUrl}
        alt={setCode}
        style={{
          width: 20,
          height: 20,
          verticalAlign: 'middle',
          filter: rarity === 'mythic'
            ? 'drop-shadow(0 0 2px orange)'
            : rarity === 'rare'
            ? 'drop-shadow(0 0 1px gold)'
            : rarity === 'uncommon'
            ? 'drop-shadow(0 0 1px silver)'
            : 'none',
        }}
      />
    </Tooltip>
  );
};

export default SetSymbol;
