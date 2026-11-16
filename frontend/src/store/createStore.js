import { combineReducers, configureStore } from '@reduxjs/toolkit'
import jobs from './jobsSlice.js'
import companies from './companiesSlice.js'
import applications from './applicationsSlice.js'
import events from './eventsSlice.js'
import session, { boundary, logoutSession } from './sessionSlice.js'
import savedItems from './savedItemsSlice.js'
import assistant from './assistantSlice.js'
import { createStudentRuntime } from './studentRuntime.js'

// `extra` carries the API clients (student fetch layer, company axios layer),
// so slices never import them directly and tests can pass fakes.
export function createAppStore(extra, preloadedState) {
  const injected = { ...extra, runtime: extra.runtime || createStudentRuntime() }
  const combined = combineReducers({ jobs, companies, applications, events, session, savedItems, assistant })
  const protectedPrefixes = ['applications/loadMine', 'applications/submit', 'events/loadRegistrations', 'events/register']
  const requests = new Map()
  const guard = ({ getState, dispatch }) => next => action => {
    if (typeof action !== 'object' || !action) return next(action)
    if (!protectedPrefixes.some(prefix => action.type.startsWith(prefix + '/'))) return next(action)
    const generation = getState().session.generation
    if (action.meta?.requestStatus === 'pending') requests.set(action.meta.requestId, generation)
    else if (action.meta?.requestId) {
      const previous = requests.get(action.meta.requestId)
      requests.delete(action.meta.requestId)
      if (previous !== generation) return action
      if (action.payload?.status === 401) { dispatch(logoutSession(generation)); return action }
    }
    // Legacy business thunk arguments are kept private at the middleware boundary.
    const arg = action.meta?.arg
    const safeArg = typeof arg === 'object' && arg ? Object.fromEntries(Object.entries(arg).filter(([key]) => key !== 'token')) : undefined
    return next({ ...action, meta: { ...action.meta, arg: safeArg } })
  }
  return configureStore({
    reducer: (state, action) => {
      if (state && boundary.match(action)) {
        const initial = combined(undefined, { type: '@@student/reset' })
        state = { ...state, applications: { ...state.applications, mine: initial.applications.mine, submit: initial.applications.submit },
          events: { ...state.events, registrations: initial.events.registrations, register: initial.events.register } }
      }
      return combined(state, action)
    },
    preloadedState,
    middleware: (getDefault) =>
      getDefault({
        thunk: { extraArgument: injected },
        // Resume uploads are File objects passed as thunk arguments; they never
        // enter state, but keep the dev check quiet for action meta.
        serializableCheck: { ignoredActionPaths: ['meta.arg.resumeFile'] },
      }).prepend(guard),
  })
}
