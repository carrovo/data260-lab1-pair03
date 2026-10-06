const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:9030'

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`

    try {
      const data = await response.json()

      if (data.detail) {
        message = data.detail
      }
    } catch {
      // Keep the default error message.
    }

    throw new Error(message)
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