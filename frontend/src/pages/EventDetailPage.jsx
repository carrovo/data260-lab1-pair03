import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Link, useLocation, useParams } from 'react-router-dom'
import {
  loadEvent,
  loadMyRegistrations,
  registerForEvent,
  selectEventDetail,
  selectMyRegistrations,
  selectRegisterState,
} from '../store/eventsSlice'
import useAuth from '../auth/useAuth'
import { formatEventDateTime } from '../eventDateTime'


function registrationErrorMessage(requestError) {
  switch (requestError.status) {
    case 401:
      return 'Your session has expired. Sign in again to register.'
    case 404:
      return 'This event is no longer available.'
    case 409:
      return 'You are already registered for this event.'
    default:
      return requestError.message || 'Unable to register for this event.'
  }
}

function EventDetailPage() {
  const { eventId } = useParams()
  const location = useLocation()
  const { accessToken, isAuthenticated, logout } = useAuth()
  const dispatch = useDispatch()
  const detail = useSelector(selectEventDetail)
  const myRegistrations = useSelector(selectMyRegistrations)
  const registerState = useSelector(selectRegisterState)
  const [removedEventId, setRemovedEventId] = useState(null)
  const [registrationError, setRegistrationError] = useState('')
  const [registrationSuccess, setRegistrationSuccess] = useState('')

  const removedAfterRegister = removedEventId === eventId
  const event = removedAfterRegister ? null : detail.item
  const loading = detail.status === 'idle' || detail.status === 'loading'
  const notFound = removedAfterRegister || detail.notFound
  const error = detail.error
    ? detail.error.message || 'Unable to load this event.'
    : ''
  const registration = isAuthenticated
    ? myRegistrations.items.find(
        (item) => String(item.event_id) === String(eventId),
      ) || null
    : null
  const checkingRegistration = myRegistrations.status === 'loading'
  const registering = registerState.status === 'loading'

  useEffect(() => {
    dispatch(loadEvent(eventId))
  }, [dispatch, eventId])

  useEffect(() => {
    if (!isAuthenticated) {
      return
    }

    dispatch(loadMyRegistrations(accessToken)).then((result) => {
      if (!loadMyRegistrations.rejected.match(result)) {
        return
      }

      if (result.payload?.status === 401) {
        setRegistrationError('Your session has expired. Sign in again to register.')
        logout()
      } else {
        setRegistrationError(
          result.payload?.message || 'Unable to check your event registrations.',
        )
      }
    })
  }, [accessToken, dispatch, eventId, isAuthenticated, logout])

  async function handleRegistration() {
    setRegistrationError('')
    setRegistrationSuccess('')

    const result = await dispatch(registerForEvent({ eventId, token: accessToken }))

    if (registerForEvent.fulfilled.match(result)) {
      setRegistrationSuccess('You are registered for this event.')
      return
    }

    const requestError = result.payload || {}
    setRegistrationError(registrationErrorMessage(requestError))

    if (requestError.status === 401) {
      logout()
    } else if (requestError.status === 404) {
      setRemovedEventId(eventId)
    } else if (requestError.status === 409) {
      const refreshed = await dispatch(loadMyRegistrations(accessToken))

      if (
        loadMyRegistrations.rejected.match(refreshed) &&
        refreshed.payload?.status === 401
      ) {
        logout()
      }
    }
  }

  return (
    <section className="page-shell detail-page event-detail-page">
      <Link className="back-link" to="/events">
        ← Back to events
      </Link>

      {loading && (
        <div className="state-panel detail-state" role="status">
          <span className="state-icon state-icon-loading" aria-hidden="true">···</span>
          <h2>Loading event details</h2>
          <p>Getting this event ready for you.</p>
        </div>
      )}

      {!loading && notFound && (
        <div className="state-panel detail-state">
          <span className="state-icon" aria-hidden="true">?</span>
          <h1>Event not found</h1>
          <p>
            This event may have been removed or the link may be incorrect.
          </p>
        </div>
      )}

      {!loading && error && (
        <div className="state-panel detail-state">
          <h1>Unable to load this event</h1>
          <p className="error-message">{error}</p>
        </div>
      )}

      {!loading && event && (
        <div className="event-detail-stack">
          <article className="surface-card event-detail-card">
            <div className="event-detail-heading">
              <div className="detail-title-group">
                <span className="detail-company-mark" aria-hidden="true">
                  {event.company?.name?.charAt(0).toUpperCase() || 'E'}
                </span>
                <div>
                <p className="page-eyebrow">UPCOMING EVENT</p>
                <h1>{event.title}</h1>
                <p className="company-name">
                  {event.company?.name || 'Independent event'}
                </p>
                </div>
              </div>
              <span className="location-badge">{event.city}</span>
            </div>

            <dl className="event-detail-schedule">
              <div>
                <dt>Starts</dt>
                <dd>{formatEventDateTime(event.starts_at)}</dd>
              </div>
              <div>
                <dt>Ends</dt>
                <dd>{formatEventDateTime(event.ends_at)}</dd>
              </div>
            </dl>

            <div className="event-description">
              <h2>Event details</h2>
              <p>{event.description}</p>
            </div>
          </article>

          <section className="surface-card registration-panel">
            <div className="panel-heading">
              <span className="panel-heading-icon" aria-hidden="true">✓</span>
              <div>
                <p className="page-eyebrow">STUDENT REGISTRATION</p>
                <h2>Attend this event</h2>
                <p>Reserve your place using your student account.</p>
              </div>
            </div>

            {!isAuthenticated && (
              <div className="sign-in-prompt">
                <p>Sign in to register for this event.</p>
                <Link
                  className="primary-link"
                  to="/login"
                  state={{ from: location }}
                >
                  Sign in to register
                </Link>
              </div>
            )}

            {isAuthenticated && checkingRegistration && (
              <p className="inline-loading" role="status">
                Checking your registration...
              </p>
            )}

            {isAuthenticated && !checkingRegistration && registration && (
              <div className="registration-confirmation">
                <div>
                  <strong>Registered</strong>
                  <p>
                    Registered {formatEventDateTime(
                      registration.registered_at,
                    )}
                  </p>
                </div>
                <span className="registered-badge">Confirmed</span>
              </div>
            )}

            {isAuthenticated && !checkingRegistration && !registration && (
              <button
                className="primary-button registration-button"
                type="button"
                disabled={registering}
                onClick={handleRegistration}
              >
                {registering ? 'Registering...' : 'Register for event'}
              </button>
            )}

            <div aria-live="polite">
              {registrationSuccess && (
                <p className="success-message">{registrationSuccess}</p>
              )}
              {registrationError && (
                <p className="error-message">{registrationError}</p>
              )}
            </div>
          </section>
        </div>
      )}
    </section>
  )
}

export default EventDetailPage
