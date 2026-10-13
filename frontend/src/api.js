const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:9030'

function getErrorMessage(data, fallbackMessage) {
  if (typeof data.detail === 'string') {
    return data.detail
  }

  if (Array.isArray(data.detail)) {
    return data.detail
      .map((error) =>
        error.msg?.replace(/^Value error, /, ''),
      )
      .filter(Boolean)
      .join(' ')
  }

  return fallbackMessage
}

async function apiRequest(
  path,
  { token, responseType = 'json', ...options } = {},
) {
  const headers = new Headers(options.headers)

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`

    try {
      const data = await response.json()

      message = getErrorMessage(data, message)
    } catch {
      // Keep the default error message.
    }

    const requestError = new Error(message)
    requestError.status = response.status
    throw requestError
  }

  if (responseType === 'blob') {
    return response.blob()
  }

  return response.json()
}

export function fetchJobs({ keyword = '', city = '' } = {}) {
  const parameters = new URLSearchParams()

  if (keyword.trim()) {
    parameters.set('keyword', keyword.trim())
  }

  if (city.trim()) {
    parameters.set('city', city.trim())
  }

  const queryString = parameters.toString()
  const path = queryString ? `/jobs?${queryString}` : '/jobs'

  return apiRequest(path)
}

export function fetchJob(jobId) {
  return apiRequest(`/jobs/${encodeURIComponent(jobId)}`)
}

export function signupStudent(studentData) {
  return apiRequest('/auth/signup', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(studentData),
  })
}

export function loginStudent(credentials) {
  return apiRequest('/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(credentials),
  })
}

export function fetchCurrentStudent(token) {
  return apiRequest('/auth/me', { token })
}

export function submitApplication(jobId, resumeFile, token) {
  const formData = new FormData()

  formData.append('resume', resumeFile)

  return apiRequest(
    `/jobs/${encodeURIComponent(jobId)}/applications`,
    {
      method: 'POST',
      body: formData,
      token,
    },
  )
}

export function fetchMyApplications(token, applicationStatus = '') {
  const parameters = new URLSearchParams()

  if (applicationStatus) {
    parameters.set('status', applicationStatus)
  }

  const queryString = parameters.toString()
  const path = queryString
    ? `/applications/me?${queryString}`
    : '/applications/me'

  return apiRequest(path, { token })
}

export function fetchApplicationResume(applicationId, token) {
  return apiRequest(
    `/applications/${encodeURIComponent(applicationId)}/resume`,
    {
      responseType: 'blob',
      token,
    },
  )
}

export function fetchEvents(keyword = '') {
  const parameters = new URLSearchParams()

  if (keyword.trim()) {
    parameters.set('keyword', keyword.trim())
  }

  const queryString = parameters.toString()
  const path = queryString ? `/events?${queryString}` : '/events'

  return apiRequest(path)
}

export function fetchEvent(eventId) {
  return apiRequest(`/events/${encodeURIComponent(eventId)}`)
}

export function registerForEvent(eventId, token) {
  return apiRequest(
    `/events/${encodeURIComponent(eventId)}/registrations`,
    {
      method: 'POST',
      token,
    },
  )
}

export function fetchMyRegistrations(token) {
  return apiRequest('/registrations/me', { token })
}
