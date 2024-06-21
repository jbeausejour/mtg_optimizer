const { useState } = React;

const CardForm = () => {
  const [cardList, setCardList] = useState('');
  const [result, setResult] = useState(null);

  const handleFetchCard = async (e) => {
    e.preventDefault();
    const response = await fetch(`/fetch_card?name=${cardList}`);
    const data = await response.json();
    setResult(data);
  };

  const handleOptimize = async (e) => {
    e.preventDefault();
    const cardArray = cardList.split('\n').map(card => card.trim());
    const response = await fetch('/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_list: cardArray })
    });
    const data = await response.json();
    setResult(data);
  };

  return (
    <div>
      <form onSubmit={handleFetchCard}>
        <textarea 
          value={cardList} 
          onChange={(e) => setCardList(e.target.value)} 
          placeholder="Enter card name or list, one per line" 
          rows="10" cols="30"
        />
        <button type="submit">Fetch Card Details</button>
        <button type="button" onClick={handleOptimize}>Optimize Purchases</button>
      </form>
      {result && (
        <div>
          <h3>Results</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

const Dashboard = () => {
  return (
    <div>
      <h1>MTG Optimizer Dashboard</h1>
      <CardForm />
    </div>
  );
};

ReactDOM.render(<Dashboard />, document.getElementById('root'));
