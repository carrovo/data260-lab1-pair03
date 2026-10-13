import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchEvents } from '../api'
import { formatEventDateTime } from '../eventDateTime'


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
    <section className="events-page">
      <div className="page-heading">
        <h1>Upcoming events</h1>
        <p>Discover career fairs, workshops, and student events.</p>
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
        <button type="submit" disabled={loading}>
          {loading ? 'Loading...' : 'Search'}
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}

      {loading && (
        <div className="events-state" role="status">
          Loading upcoming events...
        </div>
      )}

      {!loading && !error && events.length === 0 && (
        <div className="events-state">
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
              <article className="event-card">
                <div className="event-card-heading">
                  <div>
                    <h2>{event.title}</h2>
                    <p className="company-name">
                      {event.company?.name || 'Independent event'}
                    </p>
                  </div>
                  <span className="event-city">{event.city}</span>
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
