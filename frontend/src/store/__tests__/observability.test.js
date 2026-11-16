import test from 'node:test'
import assert from 'node:assert/strict'
import { safeUsage, safeCompaction, contextWarning } from '../observability.js'
import { createAppStore } from '../createStore.js'
import { createStudentRuntime } from '../studentRuntime.js'
import { authenticate, logoutSession } from '../sessionSlice.js'
import { sendChat, startNewConversation } from '../assistantSlice.js'

const usage = { model_calls: 2, prompt_tokens: 1100, completion_tokens: 30, total_tokens: 1130,
  latest_context_tokens: 710, context_capacity: 1000, context_percent: 71, context_is_estimate: true,
  calls: [{ index: 1, prompt_tokens: 400, completion_tokens: 20, source: 'ollama', purpose: 'agent' },
    { index: 2, prompt_tokens: 700, completion_tokens: 10, source: 'ollama', purpose: 'agent' }] }

test('latest-call context differs from overlapping request totals and warnings require known capacity', () => {
  const result = safeUsage(usage)
  assert.equal(result.total_tokens, 1130)
  assert.equal(result.latest_context_tokens, 710)
  assert.equal(result.context_percent, 71)
  assert.equal(contextWarning(result), true)
  assert.equal(contextWarning({ ...result, context_percent: 70 }), false)
  assert.equal(contextWarning({ ...result, context_percent: 70.01 }), true)
  assert.equal(contextWarning({ ...result, context_capacity: null }), false)
  assert.equal(contextWarning(safeUsage({})), false)
  assert.equal(safeUsage({}).total_tokens, null)
  assert.equal(safeUsage({}).context_percent, null)
})

test('metrics whitelist excludes secrets and distinguishes unavailable and synthetic observations', () => {
  const result = safeUsage({ ...usage, action_token: 'not-public', calls: [{ ...usage.calls[0], authorization: 'not-public', source: 'synthetic' }] })
  assert.ok(!JSON.stringify(result).includes('not-public'))
  assert.equal(result.calls[0].source, 'synthetic')
  assert.equal(safeCompaction({ status: 'compacted', before_prompt_tokens: null, after_prompt_tokens: null }).measurement_source, 'unknown')
  assert.equal(safeCompaction({ status: 'invented' }), null)
})

test('usage is conversation scoped, survives navigation and clears on end/logout; stale metadata is discarded', async () => {
  let finish; let calls = 0
  const pending = new Promise(resolve => { finish = resolve })
  const store = createAppStore({ runtime: createStudentRuntime({ getItem: () => null, setItem: () => {}, removeItem: () => {} }), company: {}, student: {
    loginStudent: async ({ email }) => ({ student: { id: email }, access_token: 'synthetic-private' }),
    sendAssistantMessage: async payload => {
      calls++
      if (calls === 3) return pending
      return { reply: 'Synthetic', conversation_id: 'conversation', usage,
        compaction: payload.message === '/compact' ? { status: 'compacted', before_prompt_tokens: 900, after_prompt_tokens: 400, measurement_source: 'synthetic' } : null }
    }, endAssistantConversation: async () => ({ ended: true }),
  } })
  await store.dispatch(authenticate('loginStudent', { email: 'A' }))
  await store.dispatch(sendChat('Synthetic'))
  const unsubscribe = store.subscribe(() => {}); unsubscribe()
  assert.equal(store.getState().assistant.usage.total_tokens, 1130)
  await store.dispatch(sendChat('/compact'))
  assert.equal(store.getState().assistant.compaction.after_prompt_tokens, 400)
  await store.dispatch(startNewConversation())
  assert.equal(store.getState().assistant.usage, null)
  const late = store.dispatch(sendChat('Another synthetic request'))
  store.dispatch(logoutSession())
  await store.dispatch(authenticate('loginStudent', { email: 'B' }))
  finish({ reply: 'Old account', usage, conversation_id: 'old' }); await late
  assert.equal(store.getState().assistant.usage, null)
  assert.equal(store.getState().assistant.conversationId, null)
})
