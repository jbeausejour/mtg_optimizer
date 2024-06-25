import React, { useEffect, useState } from 'react';

const MainPage = () => {
  const [cards, setCards] = useState([]);
  const [sites, setSites] = useState([]);

  useEffect(() => {
    fetch('/api/cards')
      .then(response => {
        console.log('Cards response status:', response.status);
        return response.json();
      })
      .then(data => {
        console.log('Cards data:', data);
        setCards(data);
      })
      .catch(error => console.error('Error fetching cards:', error));

    fetch('/api/sites')
      .then(response => {
        console.log('Sites response status:', response.status);
        return response.json();
      })
      .then(data => {
        console.log('Sites data:', data);
        setSites(data);
      })
      .catch(error => console.error('Error fetching sites:', error));
  }, []);

  return (
    <div>
      <h1>MTG Card List</h1>
      <ul>
        {cards.map((card, index) => (
          <li key={index}>{card.card}</li>
        ))}
      </ul>

      <h1>Site List</h1>
      <ul>
        {sites.map((site, index) => (
          <li key={index}>{site.site}</li>
        ))}
      </ul>
    </div>
  );
};

export default MainPage;
