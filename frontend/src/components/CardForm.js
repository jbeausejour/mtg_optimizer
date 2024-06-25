import React, { useState } from 'react';

const CardForm = ({ addCard }) => {
  const [card, setCard] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    addCard(card);
    setCard('');
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={card}
        onChange={(e) => setCard(e.target.value)}
        placeholder="Enter card name"
      />
      <button type="submit">Add Card</button>
    </form>
  );
};

export default CardForm;
