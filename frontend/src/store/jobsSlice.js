import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import { idle, normalizeIds, toSerializableError } from './errors.js'

// Public job search and detail (students), plus the company's own postings.
export const searchJobs = createAsyncThunk(
  'jobs/search',
  async (query, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.student.fetchJobs(query))
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const loadJob = createAsyncThunk(
  'jobs/loadOne',
  async (jobId, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.student.fetchJob(jobId))
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const loadMyJobs = createAsyncThunk(
  'jobs/loadMine',
  async (_, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.company.listJobs())
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const createMyJob = createAsyncThunk(
  'jobs/createMine',
  async (payload, { extra, dispatch, rejectWithValue }) => {
    try {
      const job = normalizeIds(await extra.company.createJob(payload))
      await dispatch(loadMyJobs())
      return job
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

const initialState = {
  list: { items: [], ...idle },
  detail: { item: null, notFound: false, ...idle },
  mine: { items: [], ...idle },
  create: { ...idle },
}

const jobsSlice = createSlice({
  name: 'jobs',
  initialState,
  reducers: {
    clearCreateError(state) {
      state.create = { ...idle }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(searchJobs.pending, (state) => {
        state.list.status = 'loading'
        state.list.error = null
      })
      .addCase(searchJobs.fulfilled, (state, action) => {
        state.list = { items: action.payload, status: 'succeeded', error: null }
      })
      .addCase(searchJobs.rejected, (state, action) => {
        state.list = { items: [], status: 'failed', error: action.payload }
      })

      .addCase(loadJob.pending, (state) => {
        state.detail = { item: null, notFound: false, status: 'loading', error: null }
      })
      .addCase(loadJob.fulfilled, (state, action) => {
        state.detail = { item: action.payload, notFound: false, status: 'succeeded', error: null }
      })
      .addCase(loadJob.rejected, (state, action) => {
        const notFound = action.payload?.status === 404
        state.detail = {
          item: null,
          notFound,
          status: 'failed',
          error: notFound ? null : action.payload,
        }
      })

      .addCase(loadMyJobs.pending, (state) => {
        state.mine.status = 'loading'
        state.mine.error = null
      })
      .addCase(loadMyJobs.fulfilled, (state, action) => {
        state.mine = { items: action.payload, status: 'succeeded', error: null }
      })
      .addCase(loadMyJobs.rejected, (state, action) => {
        state.mine.status = 'failed'
        state.mine.error = action.payload
      })

      .addCase(createMyJob.pending, (state) => {
        state.create = { status: 'loading', error: null }
      })
      .addCase(createMyJob.fulfilled, (state) => {
        state.create = { status: 'succeeded', error: null }
      })
      .addCase(createMyJob.rejected, (state, action) => {
        state.create = { status: 'failed', error: action.payload }
      })
  },
})

export const { clearCreateError } = jobsSlice.actions
export default jobsSlice.reducer

export const selectJobList = (state) => state.jobs.list
export const selectJobDetail = (state) => state.jobs.detail
export const selectMyJobs = (state) => state.jobs.mine
export const selectJobCreate = (state) => state.jobs.create
