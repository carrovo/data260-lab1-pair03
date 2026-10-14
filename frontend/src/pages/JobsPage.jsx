import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { fetchJobs } from '../api'


function formatJobDate(value) {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Recently'
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(date)
}

function JobsPage() {
  const location = useLocation()
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
    <section className="page-shell jobs-page">
      <div className="page-header">
        <div className="page-header-main">
          <p className="page-eyebrow">OPPORTUNITIES</p>
          <h1>Find jobs and internships</h1>
          <p>Explore roles from employers looking for emerging talent.</p>
        </div>
      </div>

      {location.state?.successMessage && (
        <p className="success-message">
          {location.state.successMessage}
        </p>
      )}

      <section className="surface-card filter-panel">
        <div className="panel-heading">
          <span className="panel-heading-icon" aria-hidden="true">⌕</span>
          <div>
            <h2>Search opportunities</h2>
            <p>Filter by role, employer, skill, or location.</p>
          </div>
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

          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? 'Searching...' : 'Search jobs'}
          </button>
        </form>
      </section>

      {error && <p className="error-message">{error}</p>}

      {loading && (
        <div className="state-panel" role="status">
          <span className="state-icon state-icon-loading" aria-hidden="true">···</span>
          <h2>Loading opportunities</h2>
          <p>Finding the latest jobs and internships for you.</p>
        </div>
      )}

      {!loading && !error && jobs.length === 0 && (
        <div className="state-panel">
          <span className="state-icon" aria-hidden="true">⌕</span>
          <h2>No jobs matched your search</h2>
          <p>Try a broader keyword or a different city.</p>
        </div>
      )}

      {!loading && !error && jobs.length > 0 && (
        <div className="job-list">
          {jobs.map((job) => (
          <Link
            className="job-card-link"
            key={job.id}
            to={`/jobs/${job.id}`}
          >
            <article className="job-card">
              <div className="job-card-heading">
                <span className="job-company-mark" aria-hidden="true">
                  {job.company.name.charAt(0).toUpperCase()}
                </span>
                <div>
                  <h2>{job.title}</h2>
                  <p className="company-name">{job.company.name}</p>
                </div>
                <span className="location-badge">{job.city}</span>
              </div>

              <p className="job-card-description">{job.description}</p>

              <div className="job-card-meta">
                <div>
                  <span>Employer location</span>
                  <strong>{job.company.city}</strong>
                </div>
                <div>
                  <span>Posted</span>
                  <strong>{formatJobDate(job.created_at)}</strong>
                </div>
              </div>

              <span className="card-link-label">View opportunity →</span>
            </article>
          </Link>
          ))}
        </div>
      )}
    </section>
  )
}

export default JobsPage
