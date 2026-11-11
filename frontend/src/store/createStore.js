import { configureStore } from '@reduxjs/toolkit'
import jobs from './jobsSlice.js'
import companies from './companiesSlice.js'
import applications from './applicationsSlice.js'
import events from './eventsSlice.js'

// `extra` carries the API clients (student fetch layer, company axios layer),
// so slices never import them directly and tests can pass fakes.
export function createAppStore(extra, preloadedState) {
  return configureStore({
    reducer: { jobs, companies, applications, events },
    preloadedState,
    middleware: (getDefault) =>
      getDefault({
        thunk: { extraArgument: extra },
        // Resume uploads are File objects passed as thunk arguments; they never
        // enter state, but keep the dev check quiet for action meta.
        serializableCheck: { ignoredActionPaths: ['meta.arg.resumeFile'] },
      }),
  })
}
