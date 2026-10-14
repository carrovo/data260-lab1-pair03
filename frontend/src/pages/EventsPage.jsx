import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchEvents } from '../api'
import { formatEventDateTime } from '../eventDateTime'


function getEventDateParts(value) {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return { day: '—', month: 'DATE' }
  }

  return {
    day: new Intl.DateTimeFormat(undefined, { day: 'numeric' }).format(date),
    month: new Intl.DateTimeFormat(undefined, { month: 'short' })
      .format(date)
      .toUpperCase(),
  }
}

function EventsPage() {
  const [keyword, setKeyword] = useState('')
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadEvents() {
      try {
        const eventData = await fetchEvents()

        if (!cancelled) {
          setEvents(eventData)
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message || 'Unable to load events.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadEvents()

    return () => {
      cancelled = true
    }
  }, [])

  async function handleSearch(event) {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      const eventData = await fetchEvents(keyword)
      setEvents(eventData)
    } catch (requestError) {
      setEvents([])
      setError(requestError.message || 'Unable to search events.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="page-shell events-page">
      <div className="page-header">
        <div className="page-header-main">
          <p className="page-eyebrow">CAREER CONNECTIONS</p>
          <h1>Upcoming events</h1>
          <p>Discover career fairs, workshops, and employer events.</p>
        </div>
      </div>

      <section className="surface-card filter-panel event-filter-panel">
        <div className="panel-heading">
          <span className="panel-heading-icon" aria-hidden="true">⌕</span>
          <div>
            <h2>Find an event</h2>
            <p>Search upcoming events by title.</p>
          </div>
        </div>
        <form className="event-search-form" onSubmit={handleSearch}>
          <div>
            <label htmlFor="event-keyword">Event name</label>
            <input
              id="event-keyword"
              type="search"
              value={keyword}
              maxLength="100"
              placeholder="Career fair"
              onChange={(event) => setKeyword(event.target.value)}
            />
          </div>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? 'Searching...' : 'Search events'}
          </button>
        </form>
      </section>

      {error && <p className="error-message">{error}</p>}

      {loading && (
        <div className="state-panel" role="status">
          <span className="state-icon state-icon-loading" aria-hidden="true">···</span>
          <h2>Loading upcoming events</h2>
          <p>Finding ways for you to connect with employers.</p>
        </div>
      )}

      {!loading && !error && events.length === 0 && (
        <div className="state-panel">
          <span className="state-icon" aria-hidden="true">◇</span>
          <h2>No events found</h2>
          <p>Try another event name or check back for new events.</p>
        </div>
      )}

      {!loading && !error && events.length > 0 && (
        <div className="event-list">
          {events.map((event) => (
            <Link
              className="event-card-link"
              key={event.id}
              to={`/events/${event.id}`}
            >
              <article className="surface-card event-card">
                <div className="event-card-heading">
                  <span className="event-date-badge" aria-hidden="true">
                    <span>{getEventDateParts(event.starts_at).month}</span>
                    <strong>{getEventDateParts(event.starts_at).day}</strong>
                  </span>
                  <div>
                    <h2>{event.title}</h2>
                    <p className="company-name">
                      {event.company?.name || 'Independent event'}
                    </p>
                  </div>
                  <span className="location-badge">{event.city}</span>
                </div>

                <dl className="event-time-grid">
                  <div>
                    <dt>Starts</dt>
                    <dd>{formatEventDateTime(event.starts_at)}</dd>
                  </div>
                  <div>
                    <dt>Ends</dt>
                    <dd>{formatEventDateTime(event.ends_at)}</dd>
                  </div>
                </dl>

                <p className="event-description-preview">
                  {event.description}
                </p>
              </article>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}

export default EventsPage
