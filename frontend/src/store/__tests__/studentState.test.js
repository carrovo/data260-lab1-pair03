import test from 'node:test'
import assert from 'node:assert/strict'
import { createAppStore } from '../createStore.js'
import { createStudentRuntime, STUDENT_TOKEN_KEY } from '../studentRuntime.js'
import { initializeSession, authenticate, logoutSession } from '../sessionSlice.js'
import { refreshSavedItems, saveItem, unsaveItem } from '../savedItemsSlice.js'
import { sendChat, decideConfirmation, startNewConversation, selectAssistant } from '../assistantSlice.js'
import { loadMyApplications } from '../applicationsSlice.js'

const deferred = () => { let resolve; let reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const error = status => Object.assign(new Error('Unavailable'), { status })
function setup(overrides = {}, saved) {
  const values = new Map(saved ? [[STUDENT_TOKEN_KEY, saved]] : [])
  const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
  const runtime = createStudentRuntime(storage)
  const student = {
    loginStudent: async ({ email }) => ({ access_token: `private-${email}`, student: { id: email, full_name: 'Synthetic student' } }),
    fetchCurrentStudent: async () => ({ id: 'restored', full_name: 'Synthetic student' }),
    fetchSavedItems: async () => [], ...overrides,
  }
  const store = createAppStore({ student, company: {}, runtime })
  return { store, runtime, storage }
}
const login = (store, email = 'A') => store.dispatch(authenticate('loginStudent', { email, password: 'not-recorded' }))
const row = { id: 1, item_type: 'job', job_id: 7, event_id: null }

test('initialization restores existing credential privately; logout clears identity and caches', async () => {
  const { store, runtime, storage } = setup({}, 'private-restored')
  await store.dispatch(initializeSession())
  assert.equal(store.getState().session.user.id, 'restored')
  assert.equal(runtime.credential(), 'private-restored')
  assert.ok(!JSON.stringify(store.getState()).includes('private-restored'))
  await store.dispatch(logoutSession())
  assert.equal(store.getState().session.status, 'anonymous')
  assert.equal(storage.getItem(STUDENT_TOKEN_KEY), undefined)
  assert.equal(runtime.credential(), null)
  assert.deepEqual(store.getState().assistant.messages, [])
})

test('initialization without a credential makes no authenticated request', async () => {
  const { store } = setup({ fetchCurrentStudent: () => assert.fail('no token') })
  await store.dispatch(initializeSession())
  assert.equal(store.getState().session.initialized, true)
  assert.equal(store.getState().session.status, 'anonymous')
})

test('account switch clears caches; late saved/chat responses cannot restore previous account', async () => {
  const saved = deferred(); const chat = deferred()
  const { store, runtime } = setup({ fetchSavedItems: () => saved.promise, sendAssistantMessage: () => chat.promise })
  await login(store)
  const saveRequest = store.dispatch(refreshSavedItems())
  const chatRequest = store.dispatch(sendChat('Synthetic question'))
  await login(store, 'B')
  saved.resolve([row]); chat.resolve({ conversation_id: 'old', reply: 'Old reply', pending_action: { action_token: 'old-secret' } })
  await Promise.all([saveRequest, chatRequest])
  assert.equal(store.getState().session.user.id, 'B')
  assert.deepEqual(store.getState().savedItems.items, [])
  assert.deepEqual(store.getState().assistant.messages, [])
  assert.equal(runtime.pending(), null)
})

test('late login and old 401 do not replace or log out a new account', async () => {
  const first = deferred(); const saved = deferred()
  const { store } = setup({ loginStudent: ({ email }) => email === 'A' ? first.promise : Promise.resolve({ access_token: `${email}-token`, student: { id: email } }), fetchSavedItems: () => saved.promise })
  const pendingLogin = login(store)
  await login(store, 'B')
  const request = store.dispatch(refreshSavedItems())
  await login(store, 'C')
  first.resolve({ access_token: 'A-token', student: { id: 'A' } }); saved.reject(error(401))
  await Promise.all([pendingLogin, request])
  assert.equal(store.getState().session.status, 'authenticated')
  assert.equal(store.getState().session.user.id, 'C')
})

test('current 401 clears all student state and pending secrets', async () => {
  const { store, runtime } = setup({ fetchSavedItems: async () => { throw error(401) } })
  await login(store); runtime.setPending('private-action')
  await store.dispatch(refreshSavedItems())
  assert.equal(store.getState().session.status, 'anonymous')
  assert.equal(runtime.pending(), null)
})

test('saved loading deduplicates, serializes mutations and refreshes authoritative server result', async () => {
  const pending = deferred(); const calls = []
  let list = [row, { ...row, id: 2 }]
  const { store } = setup({ fetchSavedItems: () => pending.promise,
    saveItem: async (...args) => calls.push(['save', ...args]), unsaveItem: async (...args) => { calls.push(['remove', ...args]); list = [] } })
  await login(store)
  const request = store.dispatch(saveItem('job', 7))
  await store.dispatch(saveItem('job', 7))
  assert.equal(store.getState().savedItems.status, 'loading')
  pending.resolve(list); await request
  assert.equal(calls.length, 1)
  assert.equal(store.getState().savedItems.items.length, 1)
  // A second isolated response proves deletes are followed by server refresh.
  const other = setup({ fetchSavedItems: async () => list, unsaveItem: async () => { list = [] } })
  await login(other.store); await other.store.dispatch(unsaveItem('job', 7))
  assert.deepEqual(other.store.getState().savedItems.items, [])
})

test('conversation survives unsubscribe/remount and uses server ID instead of duplicate history', async () => {
  const calls = []
  const { store } = setup({ sendAssistantMessage: async payload => {
    calls.push(payload)
    return { conversation_id: 'server-thread', reply: 'Synthetic answer', conversation: [{ role: 'user', content: 'First' }, { role: 'assistant', content: 'Synthetic answer' }] }
  } })
  await login(store)
  await store.dispatch(sendChat('First'))
  const stop = store.subscribe(() => {}); stop() // route components unsubscribe; Provider remains mounted
  assert.equal(selectAssistant(store.getState()).messages.length, 2)
  await store.dispatch(sendChat('Follow up'))
  assert.deepEqual(calls[0], { conversation: [], message: 'First' })
  assert.deepEqual(calls[1], { conversation_id: 'server-thread', message: 'Follow up' })
})

for (const approved of [true, false]) test(`confirmation ${approved ? 'approval' : 'decline'} preserves private token and safe pending UI`, async () => {
  const calls = []; let refreshes = 0
  const { store, runtime, storage } = setup({ fetchSavedItems: async () => { refreshes++; return [] }, sendAssistantMessage: async payload => {
    calls.push(payload)
    return calls.length === 1 ? { conversation_id: 'thread', reply: 'Confirm save?', pending_action: {
      action_token: 'private-confirmation', tool_name: 'save_job_or_event', summary: 'Save synthetic job', item_type: 'job', item_id: 7,
    } } : { reply: approved ? 'Saved' : 'Cancelled' }
  } })
  await login(store); await store.dispatch(sendChat('Save job'))
  assert.equal(store.getState().assistant.pending.summary, 'Save synthetic job')
  assert.ok(!JSON.stringify(store.getState()).includes('private-confirmation'))
  assert.equal(storage.getItem('action_token'), undefined)
  const unsubscribe = store.subscribe(() => {}); unsubscribe()
  await store.dispatch(decideConfirmation(approved))
  assert.deepEqual(calls[1], { conversation_id: 'thread', confirmation: { action_token: 'private-confirmation', approved } })
  assert.equal(runtime.pending(), null)
  assert.equal(store.getState().assistant.pending, null)
  assert.equal(refreshes, approved ? 1 : 0)
})

test('duplicate submissions are suppressed; ended/expired conversations require an explicit new conversation', async () => {
  const pending = deferred(); let count = 0
  const { store } = setup({ sendAssistantMessage: async () => { count++; return count === 1 ? pending.promise : Promise.reject(error(404)) }, endAssistantConversation: async () => ({ ended: true }) })
  await login(store)
  const request = store.dispatch(sendChat('One')); await store.dispatch(sendChat('Two'))
  assert.equal(count, 1)
  assert.deepEqual(store.getState().assistant.messages, [{ role: 'user', content: 'One' }])
  pending.resolve({ reply: 'Answer', conversation_id: 'thread' }); await request
  await store.dispatch(sendChat('Expired'))
  assert.equal(store.getState().assistant.expired, true)
  await store.dispatch(sendChat('Blocked')); assert.equal(count, 2)
  await store.dispatch(startNewConversation())
  assert.equal(store.getState().assistant.conversationId, null)
  assert.equal(store.getState().assistant.expired, false)
})

test('business slice late results are discarded on identity change and caches reset', async () => {
  const result = deferred()
  const { store } = setup({ fetchMyApplications: () => result.promise })
  await login(store)
  const request = store.dispatch(loadMyApplications({}))
  await login(store, 'B')
  result.resolve([{ id: 1, student_id: 'A' }]); await request
  assert.deepEqual(store.getState().applications.mine.items, [])
})

test('a failed save surfaces an error; a server-confirmed end clears thread even when consolidation is unavailable', async () => {
  const { store } = setup({ saveItem: async () => { throw error(500) },
    sendAssistantMessage: async () => ({ reply: 'Answer', conversation_id: 'thread' }),
    endAssistantConversation: async () => { throw Object.assign(error(503), { ended: true }) } })
  await login(store)
  await store.dispatch(saveItem('job', 7))
  assert.equal(store.getState().savedItems.status, 'failed')
  assert.deepEqual(store.getState().savedItems.items, [])
  await store.dispatch(sendChat('Question'))
  await store.dispatch(startNewConversation())
  assert.equal(store.getState().assistant.conversationId, null)
  assert.deepEqual(store.getState().assistant.messages, [])
})

test('known credential and confirmation-token echoes never enter public state', async () => {
  const { store } = setup({ sendAssistantMessage: async () => ({
    reply: 'private-A private-confirmation', pending_action: {
      action_token: 'private-confirmation', summary: 'private-confirmation', tool_name: 'save_job_or_event', item_type: 'job', item_id: 7,
    }, conversation: [{ role: 'system', content: 'not public' }, { role: 'assistant', content: 'private-A private-confirmation' }],
  }) })
  await login(store); await store.dispatch(sendChat('Question'))
  const state = JSON.stringify(store.getState())
  assert.ok(!state.includes('private-A'))
  assert.ok(!state.includes('private-confirmation'))
  assert.equal(store.getState().assistant.messages.length, 1)
})

test('approval replaces an older saved-item refresh and discards its stale snapshot', async () => {
  const stale = deferred(); let reads = 0; let chats = 0
  const { store } = setup({ fetchSavedItems: () => ++reads === 1 ? stale.promise : Promise.resolve([row]),
    sendAssistantMessage: async () => ++chats === 1 ? { reply: 'Confirm?', pending_action: {
      action_token: 'private-confirmation', tool_name: 'save_job_or_event', item_type: 'job', item_id: 7, summary: 'Save',
    } } : { reply: 'Saved' } })
  await login(store)
  const old = store.dispatch(refreshSavedItems())
  await store.dispatch(sendChat('Save'))
  await store.dispatch(decideConfirmation(true))
  // Finish both promises: an older snapshot may arrive after the write refresh.
  stale.resolve([]); await old
  assert.equal(store.getState().savedItems.items.length, 1)
})

test('lost in-memory confirmation token requires restart without submitting a decision', async () => {
  let calls = 0; let ends = 0
  const { store, runtime } = setup({ sendAssistantMessage: async () => {
    calls++
    return { reply: 'Confirm?', conversation_id: 'thread', pending_action: {
      action_token: 'private-confirmation', summary: 'Save', tool_name: 'save_job_or_event', item_type: 'job', item_id: 7,
    } }
  }, endAssistantConversation: async () => { ends++; return { ended: true } } })
  await login(store); await store.dispatch(sendChat('Save'))
  runtime.setPending(null)
  await store.dispatch(decideConfirmation(true))
  assert.equal(calls, 1)
  assert.equal(store.getState().assistant.pending, null)
  assert.equal(store.getState().assistant.restartRequired, true)
  assert.match(store.getState().assistant.error, /Start a new conversation/)
  await store.dispatch(sendChat('Blocked until restart'))
  assert.equal(calls, 1)
  await store.dispatch(startNewConversation())
  assert.equal(ends, 1)
  assert.equal(store.getState().assistant.restartRequired, false)
})
