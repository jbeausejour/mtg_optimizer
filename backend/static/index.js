const { useState, useEffect } = React;

const App = () => {
  const [siteList, setSiteList] = useState([]);
  const [buyList, setBuyList] = useState([]);

  useEffect(() => {
    fetch('/get_site_list')
      .then(response => response.json())
      .then(data => setSiteList(data));

    fetch('/get_buy_list')
      .then(response => response.json())
      .then(data => setBuyList(data));
  }, []);

  return (
    <div>
      <h1>MTG Optimizer</h1>
      <h2>Site List</h2>
      <ul>
        {siteList.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
      <h2>Buy List</h2>
      <ul>
        {buyList.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
};

ReactDOM.render(<App />, document.getElementById('root'));
