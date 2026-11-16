import test from 'node:test'
import assert from 'node:assert/strict'
import * as api from '../../api.js'

test('authenticated client reads conversation header, handles 204 and ended publication failure', async t => {
  let request
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    request = { url, ...options }
    return new Response(JSON.stringify({ reply: 'Synthetic reply', conversation: [] }), { headers: { 'X-Conversation-Id': 'server-id' } })
  })
  const result = await api.sendAssistantMessage({ message: 'Synthetic' }, 'private-test-token')
  assert.equal(result.conversation_id, 'server-id')
  assert.equal(request.headers.get('Authorization'), 'Bearer private-test-token')
  globalThis.fetch.mock.mockImplementation(async () => new Response(null, { status: 204 }))
  assert.equal(await api.unsaveItem('job', 1, 'private-test-token'), null)
  globalThis.fetch.mock.mockImplementation(async () => new Response(JSON.stringify({ detail: { ended: true, consolidation_enqueued: false } }), { status: 503 }))
  await assert.rejects(api.endAssistantConversation('server-id', 'private-test-token'), error => error.status === 503 && error.ended)
})
