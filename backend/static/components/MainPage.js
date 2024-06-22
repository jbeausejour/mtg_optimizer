import React, { useState, useEffect } from 'react';

const MainPage = () => {
  const [cardList, setCardList] = useState('');
  
  useEffect(() => {
    fetchCardList();
  }, []);
  
  const fetchCardList = async () => {
    const response = await fetch('/get_card_list');
    const data = await response.text();
    setCardList(data);
  };

  const handleClearList = () => {
    setCardList('');
  };

  const handleSearch = () => {
    console.log('Search initiated with card list:', cardList);
    // Implement your search logic here
  };

  return (
    <div>
      <h1>Welcome to MTG Optimizer</h1>
      <textarea
        rows="10"
        cols="50"
        value={cardList}
        onChange={(e) => setCardList(e.target.value)}
        placeholder="Enter your card list here..."
      />
      <br />
      <button onClick={handleClearList}>Clear List</button>
      <button onClick={handleSearch}>Search</button>
    </div>
  );
};

export default MainPage;
