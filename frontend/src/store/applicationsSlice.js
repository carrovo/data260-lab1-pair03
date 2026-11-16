import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import { idle, normalizeIds, toSerializableError } from './errors.js'

// Student: my applications and submitting one. Company: applicants for a job
// and changing an application's status.
export const loadMyApplications = createAsyncThunk(
  'applications/loadMine',
  async ({ token, status = '' }, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.student.fetchMyApplications(token, status))
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const submitJobApplication = createAsyncThunk(
  'applications/submit',
  async ({ jobId, resumeFile, token }, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(
        await extra.student.submitApplication(jobId, resumeFile, token),
      )
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const loadApplicants = createAsyncThunk(
  'applications/loadApplicants',
  async (jobId, { extra, rejectWithValue }) => {
    try {
      return { jobId: String(jobId), items: normalizeIds(await extra.company.listApplicants(jobId)) }
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const updateApplicantStatus = createAsyncThunk(
  'applications/updateStatus',
  async ({ applicationId, status, jobId }, { extra, dispatch, rejectWithValue }) => {
    try {
      await extra.company.updateApplicationStatus(applicationId, status)
      await dispatch(loadApplicants(jobId))
      return { applicationId: String(applicationId), status }
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

const initialState = {
  mine: { items: [], ...idle },
  submit: { ...idle },
  applicants: { jobId: null, items: [], ...idle },
  statusUpdate: { ...idle },
}

const applicationsSlice = createSlice({
  name: 'applications',
  initialState,
  reducers: {
    clearSubmitState(state) {
      state.submit = { ...idle }
    },
    clearStatusError(state) {
      state.statusUpdate = { ...idle }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadMyApplications.pending, (state) => {
        state.mine.status = 'loading'
        state.mine.error = null
      })
      .addCase(loadMyApplications.fulfilled, (state, action) => {
        state.mine = { items: action.payload, status: 'succeeded', error: null }
      })
      .addCase(loadMyApplications.rejected, (state, action) => {
        state.mine = { items: [], status: 'failed', error: action.payload }
      })

      .addCase(submitJobApplication.pending, (state) => {
        state.submit = { status: 'loading', error: null }
      })
      .addCase(submitJobApplication.fulfilled, (state, action) => {
        state.submit = { status: 'succeeded', error: null }
        state.mine.items = [
          action.payload,
          ...state.mine.items.filter((item) => item.id !== action.payload.id),
        ]
      })
      .addCase(submitJobApplication.rejected, (state, action) => {
        state.submit = { status: 'failed', error: action.payload }
      })

      .addCase(loadApplicants.pending, (state) => {
        state.applicants.status = 'loading'
        state.applicants.error = null
      })
      .addCase(loadApplicants.fulfilled, (state, action) => {
        state.applicants = {
          jobId: action.payload.jobId,
          items: action.payload.items,
          status: 'succeeded',
          error: null,
        }
      })
      .addCase(loadApplicants.rejected, (state, action) => {
        state.applicants.status = 'failed'
        state.applicants.error = action.payload
      })

      .addCase(updateApplicantStatus.pending, (state) => {
        state.statusUpdate = { status: 'loading', error: null }
      })
      .addCase(updateApplicantStatus.fulfilled, (state) => {
        state.statusUpdate = { status: 'succeeded', error: null }
      })
      .addCase(updateApplicantStatus.rejected, (state, action) => {
        state.statusUpdate = { status: 'failed', error: action.payload }
      })
  },
})

export const { clearSubmitState, clearStatusError } = applicationsSlice.actions
export default applicationsSlice.reducer

export const selectMyApplications = (state) => state.applications.mine
export const selectSubmitState = (state) => state.applications.submit
export const selectApplicants = (state) => state.applications.applicants
export const selectStatusUpdate = (state) => state.applications.statusUpdate
export const selectApplicationForJob = (state, jobId) =>
  state.applications.mine.items.find(
    (item) => String(item.job_id) === String(jobId),
  ) || null
