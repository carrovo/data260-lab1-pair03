import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchMyRegistrations } from '../api'
import useAuth from '../auth/useAuth'
import { formatEventDateTime } from '../eventDateTime'


function RegistrationsPage() {
  const { accessToken, logout } = useAuth()
  const [registrations, setRegistrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadRegistrations() {
      setLoading(true)
      setError('')

      try {
        const registrationData = await fetchMyRegistrations(accessToken)

        if (!cancelled) {
          setRegistrations(registrationData)
        }
      } catch (requestError) {
        if (!cancelled) {
          setRegistrations([])

          if (requestError.status === 401) {
            logout()
          } else {
            setError(
              requestError.message || 'Unable to load your registrations.',
            )
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadRegistrations()

    return () => {
      cancelled = true
    }
  }, [accessToken, logout])

  return (
    <section className="registrations-page">
      <div className="page-heading">
        <h1>My registrations</h1>
        <p>Review the events you have registered to attend.</p>
      </div>

      {loading && (
        <div className="events-state" role="status">
          Loading registrations...
        </div>
      )}

      {!loading && error && <p className="error-message">{error}</p>}

      {!loading && !error && registrations.length === 0 && (
        <div className="events-state">
          <h2>No registrations yet</h2>
          <p>Your registered events will appear here.</p>
          <Link className="primary-link" to="/events">
            Browse events
          </Link>
        </div>
      )}

      {!loading && !error && registrations.length > 0 && (
        <div className="registration-list">
          {registrations.map((registration) => (
            <article className="registration-card" key={registration.id}>
              <div className="registration-card-heading">
                <div>
                  <Link
                    className="application-job-link"
                    to={`/events/${registration.event.id}`}
                  >
                    {registration.event.title}
                  </Link>
                  <p className="company-name">
                    {registration.event.company?.name || 'Independent event'}
                  </p>
                </div>
                <span className="registered-badge">Registered</span>
              </div>

              <dl className="registration-details">
                <div>
                  <dt>City</dt>
                  <dd>{registration.event.city}</dd>
                </div>
                <div>
                  <dt>Starts</dt>
                  <dd>
                    {formatEventDateTime(registration.event.starts_at)}
                  </dd>
                </div>
                <div>
                  <dt>Ends</dt>
                  <dd>{formatEventDateTime(registration.event.ends_at)}</dd>
                </div>
                <div>
                  <dt>Registered</dt>
                  <dd>{formatEventDateTime(registration.registered_at)}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export default RegistrationsPage
