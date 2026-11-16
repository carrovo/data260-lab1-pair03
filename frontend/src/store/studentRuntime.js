// Store-lifetime secrets. Never part of actions, state, DevTools or persistence.
export const STUDENT_TOKEN_KEY = 'student_access_token'

export function createStudentRuntime(storage = globalThis.localStorage) {
  let credential = null
  let pendingToken = null
  return {
    savedCredential: () => storage?.getItem(STUDENT_TOKEN_KEY),
    credential: () => credential,
    establish(value) { credential = value; storage?.setItem(STUDENT_TOKEN_KEY, value) },
    clear() { credential = null; pendingToken = null; storage?.removeItem(STUDENT_TOKEN_KEY) },
    pending: () => pendingToken,
    setPending(value) { pendingToken = value || null },
  }
}

export function publicText(value = '', secrets = []) {
  let text = String(value)
  for (const secret of secrets) if (secret) text = text.replaceAll(secret, '[redacted]')
  return text.replace(/Bearer\s+\S+|\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/gi, '[redacted]')
    .replace(/\b(password|action_token|access_token|api_key)\s*[:=]\s*\S+/gi, '$1: [redacted]')
}

export function publicMessages(messages, secrets = []) {
  return (Array.isArray(messages) ? messages : []).filter(m =>
    ['user', 'assistant'].includes(m?.role) && typeof m.content === 'string' && m.content.trim(),
  ).map(m => ({ role: m.role, content: publicText(m.content, secrets).slice(0, 8000) })).slice(-40)
}
