import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import { idle, normalizeIds, toSerializableError } from './errors.js'

// Student: event search, detail, my registrations, registering.
// Company: own events, creating one, and the registrants of an event.
export const searchEvents = createAsyncThunk(
  'events/search',
  async (keyword, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.student.fetchEvents(keyword))
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const loadEvent = createAsyncThunk(
  'events/loadOne',
  async (eventId, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.student.fetchEvent(eventId))
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const loadMyRegistrations = createAsyncThunk(
  'events/loadRegistrations',
  async (token, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.student.fetchMyRegistrations(token))
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const registerForEvent = createAsyncThunk(
  'events/register',
  async ({ eventId, token }, { extra, dispatch, rejectWithValue }) => {
    try {
      const result = normalizeIds(await extra.student.registerForEvent(eventId, token))
      await dispatch(loadMyRegistrations(token))
      return result
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const loadMyEvents = createAsyncThunk(
  'events/loadMine',
  async (_, { extra, rejectWithValue }) => {
    try {
      return normalizeIds(await extra.company.listEvents())
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const createMyEvent = createAsyncThunk(
  'events/createMine',
  async (payload, { extra, dispatch, rejectWithValue }) => {
    try {
      const event = normalizeIds(await extra.company.createEvent(payload))
      await dispatch(loadMyEvents())
      return event
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

export const loadRegistrants = createAsyncThunk(
  'events/loadRegistrants',
  async (eventId, { extra, rejectWithValue }) => {
    try {
      return {
        eventId: String(eventId),
        items: normalizeIds(await extra.company.listRegistrants(eventId)),
      }
    } catch (error) {
      return rejectWithValue(toSerializableError(error))
    }
  },
)

const initialState = {
  list: { items: [], ...idle },
  detail: { item: null, notFound: false, ...idle },
  registrations: { items: [], ...idle },
  register: { ...idle },
  mine: { items: [], ...idle },
  create: { ...idle },
  registrants: { eventId: null, items: [], ...idle },
}

const eventsSlice = createSlice({
  name: 'events',
  initialState,
  reducers: {
    clearRegisterState(state) {
      state.register = { ...idle }
    },
    clearCreateEventState(state) {
      state.create = { ...idle }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(searchEvents.pending, (state) => {
        state.list.status = 'loading'
        state.list.error = null
      })
      .addCase(searchEvents.fulfilled, (state, action) => {
        state.list = { items: action.payload, status: 'succeeded', error: null }
      })
      .addCase(searchEvents.rejected, (state, action) => {
        state.list = { items: [], status: 'failed', error: action.payload }
      })

      .addCase(loadEvent.pending, (state) => {
        state.detail = { item: null, notFound: false, status: 'loading', error: null }
      })
      .addCase(loadEvent.fulfilled, (state, action) => {
        state.detail = { item: action.payload, notFound: false, status: 'succeeded', error: null }
      })
      .addCase(loadEvent.rejected, (state, action) => {
        const notFound = action.payload?.status === 404
        state.detail = {
          item: null,
          notFound,
          status: 'failed',
          error: notFound ? null : action.payload,
        }
      })

      .addCase(loadMyRegistrations.pending, (state) => {
        state.registrations.status = 'loading'
        state.registrations.error = null
      })
      .addCase(loadMyRegistrations.fulfilled, (state, action) => {
        state.registrations = { items: action.payload, status: 'succeeded', error: null }
      })
      .addCase(loadMyRegistrations.rejected, (state, action) => {
        state.registrations = { items: [], status: 'failed', error: action.payload }
      })

      .addCase(registerForEvent.pending, (state) => {
        state.register = { status: 'loading', error: null }
      })
      .addCase(registerForEvent.fulfilled, (state) => {
        state.register = { status: 'succeeded', error: null }
      })
      .addCase(registerForEvent.rejected, (state, action) => {
        state.register = { status: 'failed', error: action.payload }
      })

      .addCase(loadMyEvents.pending, (state) => {
        state.mine.status = 'loading'
        state.mine.error = null
      })
      .addCase(loadMyEvents.fulfilled, (state, action) => {
        state.mine = { items: action.payload, status: 'succeeded', error: null }
      })
      .addCase(loadMyEvents.rejected, (state, action) => {
        state.mine.status = 'failed'
        state.mine.error = action.payload
      })

      .addCase(createMyEvent.pending, (state) => {
        state.create = { status: 'loading', error: null }
      })
      .addCase(createMyEvent.fulfilled, (state) => {
        state.create = { status: 'succeeded', error: null }
      })
      .addCase(createMyEvent.rejected, (state, action) => {
        state.create = { status: 'failed', error: action.payload }
      })

      .addCase(loadRegistrants.pending, (state) => {
        state.registrants.status = 'loading'
        state.registrants.error = null
      })
      .addCase(loadRegistrants.fulfilled, (state, action) => {
        state.registrants = {
          eventId: action.payload.eventId,
          items: action.payload.items,
          status: 'succeeded',
          error: null,
        }
      })
      .addCase(loadRegistrants.rejected, (state, action) => {
        state.registrants.status = 'failed'
        state.registrants.error = action.payload
      })
  },
})

export const { clearRegisterState, clearCreateEventState } = eventsSlice.actions
export default eventsSlice.reducer

export const selectEventList = (state) => state.events.list
export const selectEventDetail = (state) => state.events.detail
export const selectMyRegistrations = (state) => state.events.registrations
export const selectRegisterState = (state) => state.events.register
export const selectMyEvents = (state) => state.events.mine
export const selectEventCreate = (state) => state.events.create
export const selectRegistrants = (state) => state.events.registrants
export const selectIsRegistered = (state, eventId) =>
  state.events.registrations.items.some(
    (item) => String(item.event_id) === String(eventId),
  )
