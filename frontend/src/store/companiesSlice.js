import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import { idle, normalizeIds, toSerializableError } from './errors.js'

// The signed-in company's profile.
export const loadCompanyProfile = createAsyncThunk(
  'companies/loadProfile',
  async (_, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.company.getProfile())
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const saveCompanyProfile = createAsyncThunk(
  'companies/saveProfile',
  async (payload, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.company.saveProfile(payload))
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

const initialState = {
  profile: { data: null, ...idle },
  save: { ...idle },
}

const companiesSlice = createSlice({
  name: 'companies',
  initialState,
  reducers: {
    clearSaveState(state) {
      state.save = { ...idle }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadCompanyProfile.pending, (state) => {
        state.profile.status = 'loading'
        state.profile.error = null
      })
      .addCase(loadCompanyProfile.fulfilled, (state, action) => {
        state.profile = { data: action.payload, status: 'succeeded', error: null }
      })
      .addCase(loadCompanyProfile.rejected, (state, action) => {
        state.profile = { data: null, status: 'failed', error: action.payload }
      })

      .addCase(saveCompanyProfile.pending, (state) => {
        state.save = { status: 'loading', error: null }
      })
      .addCase(saveCompanyProfile.fulfilled, (state, action) => {
        state.save = { status: 'succeeded', error: null }
        if (action.payload && typeof action.payload === 'object') {
          state.profile.data = action.payload
        }
      })
      .addCase(saveCompanyProfile.rejected, (state, action) => {
        state.save = { status: 'failed', error: action.payload }
      })
  },
})

export const { clearSaveState } = companiesSlice.actions
export default companiesSlice.reducer

export const selectCompanyProfile = (state) => state.companies.profile
export const selectCompanySave = (state) => state.companies.save
