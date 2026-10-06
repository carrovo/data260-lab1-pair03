import { useEffect, useState } from 'react'
import { fetchJobs } from '../api'

function JobsPage() {
  const [keyword, setKeyword] = useState('')
  const [city, setCity] = useState('')
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadJobs() {
      try {
        const data = await fetchJobs()

        if (!cancelled) {
          setJobs(data)
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadJobs()

    return () => {
      cancelled = true
    }
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      const data = await fetchJobs({ keyword, city })
      setJobs(data)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
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
            type="search"
            placeholder="Data analyst"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </div>

        <div>
          <label htmlFor="job-city">City</label>
          <input
            id="job-city"
            type="search"
            placeholder="San Jose"
            value={city}
            onChange={(event) => setCity(event.target.value)}
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading ? 'Loading...' : 'Search'}
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}

      {!loading && !error && jobs.length === 0 && (
        <div className="empty-state">
          No jobs matched your search.
        </div>
      )}

      <div className="job-list">
        {jobs.map((job) => (
          <article className="job-card" key={job.id}>
            <div className="job-card-heading">
              <h2>{job.title}</h2>
              <span>{job.city}</span>
            </div>

            <p className="company-name">
              {job.company.name} · {job.company.city}
            </p>

            <p>{job.description}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

export default JobsPage