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

async function apiRequest(path, { token, ...options } = {}) {
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
