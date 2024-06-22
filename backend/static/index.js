const { useState, useEffect } = React;

const App = () => {
  const [siteList, setSiteList] = useState([]);
  const [newSite, setNewSite] = useState({ name: '', url: '', parse_method: '', type: '' });

  useEffect(() => {
    fetchSiteList();
  }, []);

  const fetchSiteList = async () => {
    const response = await fetch('/get_site_list');
    const data = await response.json();
    setSiteList(data);
  };

  const handleAddSite = async (e) => {
    e.preventDefault();
    const response = await fetch('/add_site', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSite)
    });
    if (response.ok) {
      setNewSite({ name: '', url: '', parse_method: '', type: '' });
      fetchSiteList();
    }
  };

  const handleDeleteSite = async (id) => {
    const response = await fetch(`/delete_site/${id}`, {
      method: 'DELETE'
    });
    if (response.ok) {
      fetchSiteList();
    }
  };

  return (
    <div>
      <h1>MTG Optimizer</h1>
      <h2>Site List</h2>
      <ul>
        {siteList.map((item, index) => (
          <li key={index}>
            <strong>{item.name}</strong> ({item.type}): {item.url}
            <button onClick={() => handleDeleteSite(item.id)}>Delete</button>
          </li>
        ))}
      </ul>
      <h2>Add New Site</h2>
      <form onSubmit={handleAddSite}>
        <input
          type="text"
          placeholder="Name"
          value={newSite.name}
          onChange={(e) => setNewSite({ ...newSite, name: e.target.value })}
          required
        />
        <input
          type="text"
          placeholder="URL"
          value={newSite.url}
          onChange={(e) => setNewSite({ ...newSite, url: e.target.value })}
          required
        />
        <input
          type="text"
          placeholder="Parse Method"
          value={newSite.parse_method}
          onChange={(e) => setNewSite({ ...newSite, parse_method: e.target.value })}
          required
        />
        <input
          type="text"
          placeholder="Type"
          value={newSite.type}
          onChange={(e) => setNewSite({ ...newSite, type: e.target.value })}
          required
        />
        <button type="submit">Add Site</button>
      </form>
    </div>
  );
};

ReactDOM.render(<App />, document.getElementById('root'));
