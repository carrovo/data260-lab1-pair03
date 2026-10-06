function JobsPage() {
    function handleSubmit(event) {
      event.preventDefault()
    }
  
    return (
      <section>
        <div className="page-heading">
          <h1>Find jobs and internships</h1>
          <p>Search by keyword, job title, company, or city.</p>
        </div>
  
        <form className="search-form" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="keyword">Keyword</label>
            <input
              id="keyword"
              name="keyword"
              type="search"
              placeholder="Data analyst"
            />
          </div>
  
          <div>
            <label htmlFor="job-city">City</label>
            <input
              id="job-city"
              name="city"
              type="search"
              placeholder="San Jose"
            />
          </div>
  
          <button type="submit">Search</button>
        </form>
  
        <div className="empty-state">
          Job results will appear here.
        </div>
      </section>
    )
  }
  
  export default JobsPage