import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import {
  fetchJob,
  fetchMyApplications,
  submitApplication,
} from '../api'
import useAuth from '../auth/useAuth'


const MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024

function formatCreatedDate(createdAt) {
  const createdDate = new Date(createdAt)

  if (Number.isNaN(createdDate.getTime())) {
    return null
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'long',
  }).format(createdDate)
}

function validateResumeFile(file) {
  if (!file) {
    return 'Select a PDF resume before applying.'
  }

  if (!file.name.toLowerCase().endsWith('.pdf')) {
    return 'Your resume filename must end in .pdf.'
  }

  if (file.type && file.type !== 'application/pdf') {
    return 'Your resume must use the application/pdf file type.'
  }

  if (file.size > MAX_RESUME_SIZE_BYTES) {
    return 'Your resume must be 5 MiB or smaller.'
  }

  return ''
}

function applicationErrorMessage(requestError) {
  switch (requestError.status) {
    case 401:
      return 'Your session has expired. Sign in again to apply.'
    case 404:
      return 'This job is no longer available.'
    case 409:
      return 'You have already applied to this job.'
    case 413:
      return 'Your resume is larger than the 5 MiB limit.'
    case 422:
      return requestError.message || 'The selected file is not a valid PDF.'
    default:
      return requestError.message || 'Unable to submit your application.'
  }
}

function JobDetailPage() {
  const { jobId } = useParams()
  const location = useLocation()
  const { accessToken, isAuthenticated, logout } = useAuth()
  const resumeInputRef = useRef(null)
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)
  const [resumeFile, setResumeFile] = useState(null)
  const [application, setApplication] = useState(null)
  const [checkingApplication, setCheckingApplication] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [applicationError, setApplicationError] = useState('')
  const [applicationSuccess, setApplicationSuccess] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadJob() {
      setLoading(true)
      setError('')
      setNotFound(false)

      try {
        const jobData = await fetchJob(jobId)

        if (!cancelled) {
          setJob(jobData)
        }
      } catch (requestError) {
        if (!cancelled) {
          setJob(null)

          if (requestError.status === 404) {
            setNotFound(true)
          } else {
            setError(requestError.message)
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadJob()

    return () => {
      cancelled = true
    }
  }, [jobId])

  useEffect(() => {
    if (!isAuthenticated) {
      return undefined
    }

    let cancelled = false

    async function loadExistingApplication() {
      setCheckingApplication(true)
      setApplicationError('')

      try {
        const applications = await fetchMyApplications(accessToken)
        const existingApplication = applications.find(
          (item) => String(item.job_id) === String(jobId),
        )

        if (!cancelled) {
          setApplication(existingApplication || null)
        }
      } catch (requestError) {
        if (!cancelled) {
          if (requestError.status === 401) {
            setApplicationError(
              'Your session has expired. Sign in again to apply.',
            )
            logout()
          } else {
            setApplicationError(
              requestError.message ||
                'Unable to check your existing applications.',
            )
          }
        }
      } finally {
        if (!cancelled) {
          setCheckingApplication(false)
        }
      }
    }

    loadExistingApplication()

    return () => {
      cancelled = true
    }
  }, [accessToken, isAuthenticated, jobId, logout])

  function handleResumeChange(event) {
    const selectedFile = event.target.files?.[0] || null

    setResumeFile(selectedFile)
    setApplicationSuccess('')
    setApplicationError(validateResumeFile(selectedFile))
  }

  async function handleApplicationSubmit(event) {
    event.preventDefault()

    const validationError = validateResumeFile(resumeFile)
    if (validationError) {
      setApplicationError(validationError)
      return
    }

    setSubmitting(true)
    setApplicationError('')
    setApplicationSuccess('')

    try {
      const submittedApplication = await submitApplication(
        jobId,
        resumeFile,
        accessToken,
      )

      setApplication(submittedApplication)
      setResumeFile(null)
      setApplicationSuccess(
        `Application submitted with status ${submittedApplication.status}.`,
      )

      if (resumeInputRef.current) {
        resumeInputRef.current.value = ''
      }
    } catch (requestError) {
      setApplicationError(applicationErrorMessage(requestError))

      if (requestError.status === 401) {
        logout()
      } else if (requestError.status === 404) {
        setJob(null)
        setNotFound(true)
      } else if (requestError.status === 409) {
        try {
          const applications = await fetchMyApplications(accessToken)
          const existingApplication = applications.find(
            (item) => String(item.job_id) === String(jobId),
          )

          if (existingApplication) {
            setApplication(existingApplication)
          }
        } catch (historyError) {
          if (historyError.status === 401) {
            logout()
          }
        }
      }
    } finally {
      setSubmitting(false)
    }
  }

  const createdDate = job ? formatCreatedDate(job.created_at) : null

  return (
    <section className="page-shell detail-page job-detail-page">
      <Link className="back-link" to="/jobs">
        ← Back to jobs
      </Link>

      {loading && (
        <div className="state-panel detail-state" role="status">
          <span className="state-icon state-icon-loading" aria-hidden="true">···</span>
          <h2>Loading job details</h2>
          <p>Getting this opportunity ready for you.</p>
        </div>
      )}

      {!loading && notFound && (
        <div className="state-panel detail-state">
          <span className="state-icon" aria-hidden="true">?</span>
          <h1>Job not found</h1>
          <p>
            This job may have been removed or the link may be incorrect.
          </p>
        </div>
      )}

      {!loading && error && (
        <div className="state-panel detail-state">
          <h1>Unable to load this job</h1>
          <p className="error-message">{error}</p>
        </div>
      )}

      {!loading && job && (
        <div className="job-detail-stack">
          <article className="surface-card job-detail-card">
            <div className="job-detail-heading">
              <div className="detail-title-group">
                <span className="detail-company-mark" aria-hidden="true">
                  {job.company.name.charAt(0).toUpperCase()}
                </span>
                <div>
                  <p className="page-eyebrow">JOB OPPORTUNITY</p>
                  <h1>{job.title}</h1>
                  <p className="company-name">{job.company.name}</p>
                </div>
              </div>
              <span className="location-badge">{job.city}</span>
            </div>

            <dl className="detail-meta-grid">
              <div>
                <dt>Job location</dt>
                <dd>{job.city}</dd>
              </div>
              <div>
                <dt>Company location</dt>
                <dd>{job.company.city}</dd>
              </div>
              {createdDate && (
                <div>
                  <dt>Posted</dt>
                  <dd>{createdDate}</dd>
                </div>
              )}
            </dl>

            <div className="job-description">
              <h2>Description</h2>
              <p>{job.description}</p>
            </div>
          </article>

          <section className="surface-card application-panel">
            <div className="panel-heading">
              <span className="panel-heading-icon" aria-hidden="true">↑</span>
              <div>
                <p className="page-eyebrow">STUDENT APPLICATION</p>
                <h2>Apply for this job</h2>
                <p>Submit an immutable PDF snapshot of your resume.</p>
              </div>
            </div>

            {!isAuthenticated && (
              <div className="sign-in-prompt">
                <p>Sign in to upload your PDF resume and apply.</p>
                <Link
                  className="primary-link"
                  to="/login"
                  state={{ from: location }}
                >
                  Sign in to apply
                </Link>
              </div>
            )}

            {isAuthenticated && checkingApplication && (
              <p className="inline-loading" role="status">
                Checking your application status...
              </p>
            )}

            {isAuthenticated && !checkingApplication && application && (
              <div className="application-confirmation">
                <div>
                  <strong>Application submitted</strong>
                  <p>
                    Resume: {application.resume_original_name || 'PDF resume'}
                  </p>
                </div>
                <span
                  className={`status-badge status-${application.status.toLowerCase()}`}
                >
                  {application.status}
                </span>
              </div>
            )}

            {isAuthenticated && !checkingApplication && !application && (
              <form
                className="application-form"
                onSubmit={handleApplicationSubmit}
              >
                <div className="file-field">
                  <span className="file-field-label" id="resume-label">
                    PDF resume
                  </span>
                  <input
                    aria-describedby="resume-name resume-help"
                    aria-labelledby="resume-label"
                    className="file-input-visually-hidden"
                    id="resume"
                    ref={resumeInputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={handleResumeChange}
                    required
                  />
                  <div className="file-picker-row">
                    <label
                      className="secondary-button file-picker-button"
                      htmlFor="resume"
                    >
                      Choose PDF
                    </label>
                    <span
                      className="file-picker-name"
                      id="resume-name"
                      aria-live="polite"
                    >
                      {resumeFile?.name || 'No file selected'}
                    </span>
                  </div>
                  <span id="resume-help">PDF only, up to 5 MiB.</span>
                </div>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={submitting || !resumeFile}
                >
                  {submitting ? 'Submitting...' : 'Submit application'}
                </button>
              </form>
            )}

            <div aria-live="polite">
              {applicationSuccess && (
                <p className="success-message">{applicationSuccess}</p>
              )}
              {applicationError && (
                <p className="error-message">{applicationError}</p>
              )}
            </div>
          </section>
        </div>
      )}
    </section>
  )
}

export default JobDetailPage
