import { createSlice, nanoid } from '@reduxjs/toolkit'
import { publicText } from './studentRuntime.js'

const initialState = { initialized: false, status: 'idle', user: null, generation: 0, requestId: null, error: null }
const slice = createSlice({
  name: 'session', initialState,
  reducers: {
    boundary(state) { return { ...initialState, initialized: true, status: 'anonymous', generation: state.generation + 1 } },
    starting(state, { payload }) { state.status = payload.restoring ? 'restoring' : 'loading'; state.requestId = payload.requestId; state.error = null },
    ready(state, { payload }) {
      if (state.requestId !== payload.requestId) return
      state.user = payload.user; state.status = payload.user ? 'authenticated' : 'anonymous'
      state.initialized = true; state.requestId = null; state.error = payload.error || null
    },
  },
})
export const { boundary, starting, ready } = slice.actions
export default slice.reducer
export const selectSession = state => state.session

export const logoutSession = expectedGeneration => (dispatch, getState, extra) => {
  if (expectedGeneration !== undefined && expectedGeneration !== getState().session.generation) return
  const token = extra.runtime.credential()
  extra.runtime.clear()
  dispatch(boundary())
  if (token && extra.student.logoutStudent) Promise.resolve(extra.student.logoutStudent(token)).catch(() => {})
}

// Plain thunks intentionally keep credentials out of createAsyncThunk meta.arg.
export const authenticate = (method, credentials) => async (dispatch, getState, extra) => {
  const saved = method === 'restore' ? extra.runtime.savedCredential() : null
  extra.runtime.clear()
  dispatch(boundary())
  const generation = getState().session.generation
  const requestId = nanoid()
  dispatch(starting({ requestId, restoring: method === 'restore' }))
  try {
    const result = method === 'restore'
      ? (saved ? { student: await extra.student.fetchCurrentStudent(saved), access_token: saved } : null)
      : await extra.student[method](credentials)
    if (getState().session.generation !== generation) return null
    if (result) extra.runtime.establish(result.access_token)
    const student = result?.student
    const user = student ? { id: String(student.id), full_name: publicText(student.full_name), city: publicText(student.city) } : null
    dispatch(ready({ requestId, user }))
    return { student: user }
  } catch (error) {
    if (getState().session.generation !== generation) return null
    dispatch(ready({ requestId, user: null, error: 'Unable to restore or authenticate the student session.' }))
    throw new Error(error.status === 401 ? 'Invalid or expired student session.' : 'Unable to sign in. Please try again.', { cause: error })
  }
}

export const initializeSession = () => (dispatch, getState) => {
  if (getState().session.initialized || getState().session.status === 'restoring') return
  return dispatch(authenticate('restore')).catch(() => {})
}
