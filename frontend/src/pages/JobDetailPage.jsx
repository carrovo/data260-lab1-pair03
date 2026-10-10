import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchJob } from '../api'


function formatCreatedDate(createdAt) {
  const createdDate = new Date(createdAt)

  if (Number.isNaN(createdDate.getTime())) {
    return null
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'long',
  }).format(createdDate)
}

function JobDetailPage() {
  const { jobId } = useParams()
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)

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

  const createdDate = job ? formatCreatedDate(job.created_at) : null

  return (
    <section className="job-detail-page">
      <Link className="back-link" to="/jobs">
        ← Back to jobs
      </Link>

      {loading && (
        <div className="job-detail-state" role="status">
          Loading job details...
        </div>
      )}

      {!loading && notFound && (
        <div className="job-detail-state">
          <h1>Job not found</h1>
          <p>
            This job may have been removed or the link may be incorrect.
          </p>
        </div>
      )}

      {!loading && error && (
        <div className="job-detail-state">
          <h1>Unable to load this job</h1>
          <p className="error-message">{error}</p>
        </div>
      )}

      {!loading && job && (
        <article className="job-detail-card">
          <div className="job-detail-heading">
            <div>
              <p className="job-detail-eyebrow">Job opportunity</p>
              <h1>{job.title}</h1>
              <p className="company-name">{job.company.name}</p>
            </div>
            <span className="job-city">{job.city}</span>
          </div>

          {createdDate && (
            <p className="job-created-date">Posted {createdDate}</p>
          )}

          <div className="job-description">
            <h2>Description</h2>
            <p>{job.description}</p>
          </div>
        </article>
      )}
    </section>
  )
}

export default JobDetailPage
