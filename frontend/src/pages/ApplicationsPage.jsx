import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchApplicationResume,
  fetchMyApplications,
} from '../api'
import useAuth from '../auth/useAuth'


const STATUS_OPTIONS = ['', 'Pending', 'Reviewed', 'Declined']
const OBJECT_URL_LIFETIME_MS = 60_000

function formatApplicationDate(appliedAt) {
  const applicationDate = new Date(appliedAt)

  if (Number.isNaN(applicationDate.getTime())) {
    return 'Date unavailable'
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(applicationDate)
}

function ApplicationsPage() {
  const { accessToken, logout } = useAuth()
  const [applications, setApplications] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [resumeError, setResumeError] = useState('')
  const [resumeLoadingId, setResumeLoadingId] = useState(null)
  const objectUrlsRef = useRef(new Map())

  useEffect(() => {
    const objectUrls = objectUrlsRef.current

    return () => {
      objectUrls.forEach((timeoutId, objectUrl) => {
        window.clearTimeout(timeoutId)
        URL.revokeObjectURL(objectUrl)
      })
      objectUrls.clear()
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadApplications() {
      setLoading(true)
      setError('')

      try {
        const applicationData = await fetchMyApplications(
          accessToken,
          statusFilter,
        )

        if (!cancelled) {
          setApplications(applicationData)
        }
      } catch (requestError) {
        if (!cancelled) {
          setApplications([])

          if (requestError.status === 401) {
            logout()
          } else {
            setError(
              requestError.message || 'Unable to load your applications.',
            )
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadApplications()

    return () => {
      cancelled = true
    }
  }, [accessToken, logout, statusFilter])

  async function handleViewResume(application) {
    const previewWindow = window.open('', '_blank')

    if (previewWindow) {
      previewWindow.opener = null
      previewWindow.document.title = 'Loading resume...'
      previewWindow.document.body.textContent = 'Loading resume...'
    }

    setResumeLoadingId(application.id)
    setResumeError('')

    try {
      const resumeBlob = await fetchApplicationResume(
        application.id,
        accessToken,
      )
      const objectUrl = URL.createObjectURL(resumeBlob)

      if (!previewWindow) {
        URL.revokeObjectURL(objectUrl)
        setResumeError(
          'Your browser blocked the resume preview. Allow pop-ups and try again.',
        )
        return
      }

      previewWindow.location.replace(objectUrl)

      const timeoutId = window.setTimeout(() => {
        URL.revokeObjectURL(objectUrl)
        objectUrlsRef.current.delete(objectUrl)
      }, OBJECT_URL_LIFETIME_MS)

      objectUrlsRef.current.set(objectUrl, timeoutId)
    } catch (requestError) {
      previewWindow?.close()

      if (requestError.status === 401) {
        setResumeError('Your session has expired. Please sign in again.')
        logout()
      } else if (requestError.status === 404) {
        setResumeError('The resume for this application is unavailable.')
      } else {
        setResumeError(
          requestError.message || 'Unable to open this resume.',
        )
      }
    } finally {
      setResumeLoadingId(null)
    }
  }

  return (
    <section className="page-shell applications-page">
      <div className="page-header applications-heading">
        <div className="page-header-main">
          <p className="page-eyebrow">CAREER ACTIVITY</p>
          <h1>My applications</h1>
          <p>Track your submitted applications and review your resumes.</p>
        </div>

        <div className="surface-card status-filter">
          <label htmlFor="application-status">Status</label>
          <select
            id="application-status"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status || 'All'} value={status}>
                {status || 'All'}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="state-panel" role="status">
          <span className="state-icon state-icon-loading" aria-hidden="true">···</span>
          <h2>Loading applications</h2>
          <p>Checking the latest status of your submissions.</p>
        </div>
      )}

      {!loading && error && <p className="error-message">{error}</p>}

      {resumeError && <p className="error-message">{resumeError}</p>}

      {!loading && !error && applications.length === 0 && (
        <div className="state-panel">
          <span className="state-icon" aria-hidden="true">≡</span>
          <h2>No applications found</h2>
          <p>
            {statusFilter
              ? `You have no ${statusFilter} applications.`
              : 'Applications will appear here after you apply to a job.'}
          </p>
          {!statusFilter && (
            <Link className="primary-link" to="/jobs">
              Browse jobs
            </Link>
          )}
        </div>
      )}

      {!loading && !error && applications.length > 0 && (
        <div className="application-list">
          {applications.map((application) => (
            <article className="surface-card application-card" key={application.id}>
              <div className="application-card-heading">
                <div className="application-title-group">
                  <span className="application-company-mark" aria-hidden="true">
                    {application.job.company.name.charAt(0).toUpperCase()}
                  </span>
                  <div>
                  <Link
                    className="application-job-link"
                    to={`/jobs/${application.job.id}`}
                  >
                    {application.job.title}
                  </Link>
                  <p className="company-name">
                    {application.job.company.name}
                  </p>
                  </div>
                </div>
                <span
                  className={`status-badge status-${application.status.toLowerCase()}`}
                >
                  {application.status}
                </span>
              </div>

              <dl className="application-details">
                <div>
                  <dt>City</dt>
                  <dd>{application.job.city}</dd>
                </div>
                <div>
                  <dt>Applied</dt>
                  <dd>{formatApplicationDate(application.applied_at)}</dd>
                </div>
                <div>
                  <dt>Resume</dt>
                  <dd>
                    {application.resume_original_name || 'Resume unavailable'}
                  </dd>
                </div>
              </dl>

              <button
                className="secondary-button"
                type="button"
                disabled={
                  resumeLoadingId === application.id ||
                  !application.resume_original_name
                }
                onClick={() => handleViewResume(application)}
              >
                {resumeLoadingId === application.id
                  ? 'Opening resume...'
                  : 'View Resume'}
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export default ApplicationsPage
