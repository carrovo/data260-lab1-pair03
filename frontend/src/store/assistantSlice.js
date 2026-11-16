import { createSlice, nanoid } from '@reduxjs/toolkit'
import { boundary, logoutSession } from './sessionSlice.js'
import { publicMessages, publicText } from './studentRuntime.js'
import { refreshSavedItems } from './savedItemsSlice.js'

const initialState = {
  messages: [], conversationId: null, pending: null, status: 'idle', error: null,
  requestId: null, expired: false, restartRequired: false,
}
const slice = createSlice({
  name: 'assistant', initialState,
  reducers: {
    started(state, { payload }) {
      state.requestId = payload.requestId; state.status = 'loading'; state.error = null
      if (payload.publicUserMessage) {
        state.messages = [...state.messages, { role: 'user', content: payload.publicUserMessage }].slice(-40)
      }
    },
    completed(state, { payload }) {
      if (state.requestId !== payload.requestId) return
      state.messages = payload.messages; state.conversationId = payload.conversationId
      state.pending = payload.pending; state.status = 'succeeded'; state.requestId = null
    },
    failed(state, { payload }) {
      if (state.requestId !== payload.requestId) return
      state.status = 'failed'; state.error = payload.message; state.requestId = null
      if (payload.expired) { state.expired = true; state.pending = null }
      if (payload.clearPending) state.pending = null
    },
    cleared: () => initialState,
    pendingUnavailable(state) {
      state.pending = null; state.restartRequired = true; state.status = 'failed'
      state.error = 'The confirmation is no longer available. Start a new conversation.'
    },
  },
  extraReducers: builder => builder.addCase(boundary, () => initialState),
})
export default slice.reducer
export const selectAssistant = state => state.assistant

// Functions capture private text/tokens; only sanitized public observations dispatch.
export const sendChat = message => exchange({ message })
export const decideConfirmation = approved => exchange({ approved })
function exchange(input) {
  return async (dispatch, getState, extra) => {
    const state = getState()
    const current = state.assistant
    if (state.session.status !== 'authenticated' || current.status === 'loading' || current.expired || current.restartRequired) return
    const confirming = Object.hasOwn(input, 'approved')
    if (confirming && current.pending && !extra.runtime.pending()) {
      dispatch(slice.actions.pendingUnavailable())
      return
    }
    if (confirming ? !current.pending || !extra.runtime.pending() : current.pending || !input.message?.trim() || input.message.length > 8000) return
    const generation = state.session.generation
    const requestId = nanoid()
    const token = extra.runtime.credential()
    const previousPendingToken = extra.runtime.pending()
    const history = current.conversationId
      ? { conversation_id: current.conversationId }
      : { conversation: publicMessages(current.messages) }
    const payload = confirming
      ? { ...history, confirmation: { action_token: extra.runtime.pending(), approved: input.approved } }
      : { ...history, message: input.message.trim() }
    dispatch(slice.actions.started({ requestId,
      publicUserMessage: confirming ? null : publicText(input.message.trim(), [token, previousPendingToken]),
    }))
    try {
      const result = await extra.student.sendAssistantMessage(payload, token)
      if (getState().session.generation !== generation || getState().assistant.requestId !== requestId) return
      extra.runtime.setPending(result.pending_action?.action_token)
      const action = result.pending_action
      const pending = action ? {
        summary: publicText(action.summary, [token, action.action_token]), tool_name: action.tool_name,
        item_type: action.item_type, item_id: String(action.item_id),
      } : null
      const fallback = [...current.messages, ...(!confirming ? [{ role: 'user', content: input.message.trim() }] : []),
        { role: 'assistant', content: result.reply || 'The assistant returned no response.' }]
      dispatch(slice.actions.completed({ requestId, pending,
        messages: publicMessages(result.conversation?.length ? result.conversation : fallback, [token, previousPendingToken, action?.action_token]),
        conversationId: result.conversation_id || current.conversationId,
      }))
      if (confirming && input.approved) dispatch(refreshSavedItems(null, true))
    } catch (error) {
      if (getState().session.generation !== generation || getState().assistant.requestId !== requestId) return
      if (error.status === 401) return dispatch(logoutSession(generation))
      const expired = error.status === 404 && Boolean(current.conversationId)
      const clearPending = confirming && [400, 409, 422].includes(error.status)
      if (clearPending || expired) extra.runtime.setPending(null)
      dispatch(slice.actions.failed({ requestId, expired, clearPending,
        message: expired ? 'This conversation ended or expired. Start a new conversation.'
          : publicText(error.message || 'Unable to reach the assistant. Please try again.', [token, previousPendingToken]),
      }))
    }
  }
}

export const startNewConversation = () => async (dispatch, getState, extra) => {
  const state = getState()
  if (state.assistant.status === 'loading') return
  const id = state.assistant.conversationId
  const generation = state.session.generation
  if (id && !state.assistant.expired) {
    const requestId = nanoid()
    dispatch(slice.actions.started({ requestId }))
    try {
      await extra.student.endAssistantConversation(id, extra.runtime.credential())
    } catch (error) {
      if (getState().session.generation !== generation) return
      if (error.status === 401) return dispatch(logoutSession(generation))
      if (error.status !== 404 && !error.ended) {
        dispatch(slice.actions.failed({ requestId, message: 'Could not end the conversation. Please retry.' }))
        return
      }
    }
  }
  if (getState().session.generation !== generation) return
  extra.runtime.setPending(null)
  dispatch(slice.actions.cleared())
}
