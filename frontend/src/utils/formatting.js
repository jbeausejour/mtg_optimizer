// frontend/src/utils/formatting.js

// Basic Oracle text formatter for line breaks and mana symbols
export const formatOracleText = (text) => (
    <p style={{ whiteSpace: 'pre-line' }}>{text}</p>
  );
  
  // Used to build the EDHREC URL slug
  export const formatCardName = (name) => {
    if (!name) return "";
    return name.toLowerCase().replace(/[^a-z0-9]/gi, '-').replace(/-+/g, '-');
  };
  