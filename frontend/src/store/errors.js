// Redux state must be serializable, so thrown errors (fetch Errors with a
// `status`, axios errors with a `response`) are reduced to a plain object.
// The shape keeps what the pages already read: `message`, `status`, and
// `response.data.detail` (used by components/ErrorMessage.jsx).
export function toSerializableError(error) {
  const detail = error?.response?.data?.detail
  const plainDetail =
    typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => ({ msg: String(item?.msg ?? '') }))
        : undefined

  return {
    message: error?.message || 'Something went wrong. Please try again.',
    status: error?.status ?? error?.response?.status ?? null,
    response: plainDetail === undefined ? undefined : { data: { detail: plainDetail } },
  }
}

// The API contract uses string ids (UUIDs after the MongoDB migration). While
// some services still return integers, the store converts ids to strings once,
// so pages and routes never compare a number with a string.
const ID_KEYS = [
  'id',
  'job_id',
  'company_id',
  'event_id',
  'student_id',
  'application_id',
  'registration_id',
]

export function normalizeIds(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeIds)
  }
  if (value && typeof value === 'object') {
    const result = {}
    for (const [key, item] of Object.entries(value)) {
      if (ID_KEYS.includes(key) && item !== null && item !== undefined) {
        result[key] = String(item)
      } else if (item && typeof item === 'object' && !(item instanceof Blob)) {
        result[key] = normalizeIds(item)
      } else {
        result[key] = item
      }
    }
    return result
  }
  return value
}

export const idle = { status: 'idle', error: null }
