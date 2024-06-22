import React, { useState, useEffect } from 'react';

const MainPage = () => {
  const [cardList, setCardList] = useState('');
  const [searchResult, setSearchResult] = useState(null);

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

  const handleSearch = async () => {
    const response = await fetch('/search_cards', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cardList })
    });
    const result = await response.json();
    setSearchResult(result);
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
      {searchResult && (
        <div>
          <h2>Search Results</h2>
          <pre>{JSON.stringify(searchResult, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default MainPage;
