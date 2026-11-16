import { createSlice, nanoid } from '@reduxjs/toolkit'
import { boundary, logoutSession } from './sessionSlice.js'

const initialState = { items: [], status: 'idle', error: null, requestId: null }
const slice = createSlice({
  name: 'savedItems', initialState,
  reducers: {
    loading(state, { payload }) { state.requestId = payload; state.status = 'loading'; state.error = null },
    received(state, { payload }) {
      if (state.requestId !== payload.requestId) return
      state.items = [...new Map(payload.items.map(item => [`${item.item_type}:${item.job_id ?? item.event_id}`, item])).values()]
      state.status = 'succeeded'; state.requestId = null
    },
    failed(state, { payload }) {
      if (state.requestId !== payload.requestId) return
      state.status = 'failed'; state.error = payload.error; state.requestId = null
    },
  },
  extraReducers: builder => builder.addCase(boundary, () => initialState),
})
export default slice.reducer
export const selectSavedItems = state => state.savedItems
export const selectIsSaved = (state, type, id) => state.savedItems.items.some(item =>
  item.item_type === type && String(item.job_id ?? item.event_id) === String(id))

export const refreshSavedItems = (change = null, force = false) => async (dispatch, getState, extra) => {
  if (getState().session.status !== 'authenticated' || (getState().savedItems.status === 'loading' && !force)) return
  const generation = getState().session.generation
  const requestId = nanoid()
  const token = extra.runtime.credential()
  dispatch(slice.actions.loading(requestId))
  try {
    if (change) await extra.student[change.remove ? 'unsaveItem' : 'saveItem'](change.itemType, change.itemId, token)
    if (getState().session.generation !== generation) return
    const items = await extra.student.fetchSavedItems(token)
    if (getState().session.generation !== generation) return
    dispatch(slice.actions.received({ requestId, items }))
  } catch (error) {
    if (getState().session.generation !== generation) return
    if (error.status === 401) return dispatch(logoutSession(generation))
    dispatch(slice.actions.failed({ requestId, error: 'Unable to update saved items. Please refresh and try again.' }))
  }
}
export const saveItem = (itemType, itemId) => refreshSavedItems({ itemType, itemId })
export const unsaveItem = (itemType, itemId) => refreshSavedItems({ itemType, itemId, remove: true })
