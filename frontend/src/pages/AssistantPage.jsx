import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { selectAssistant, sendChat, decideConfirmation, startNewConversation } from '../store/assistantSlice.js'
import { contextWarning } from '../store/observability.js'


const MAX_MESSAGE_LENGTH = 8000
const EXAMPLE_PROMPTS = [
  'Find data analyst jobs in San Jose.',
  'Show career events for data science majors.',
  'What jobs match my saved preferences?',
]

// The model writes **bold** Markdown; show it as bold text instead of raw asterisks.
function renderInline(text) {
  return String(text).split(/(\*\*[^*\n]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part
  )
}

function AssistantPage() {
  const dispatch = useDispatch()
  const state = useSelector(selectAssistant)
  const { messages: conversation, pending: pendingAction, error } = state
  const expired = state.expired || state.restartRequired
  const loading = state.status === 'loading'
  const statusMessage = loading ? 'Waiting for the assistant...' : pendingAction ? 'Please confirm or cancel the save.' : ''
  const [message, setMessage] = useState('')
  const conversationEndRef = useRef(null)
  useEffect(() => { conversationEndRef.current?.scrollIntoView({ block: 'nearest' }) }, [conversation, pendingAction])
  const canSend = Boolean(message.trim() && message.length <= MAX_MESSAGE_LENGTH && !loading && !pendingAction && !expired)
  function submitMessage() {
    if (!canSend) return
    dispatch(sendChat(message))
    setMessage('')
  }
  function handleSubmit(event) {
    event.preventDefault()
    submitMessage()
  }

  function handleKeyDown(event) {
    if (event.isComposing || event.nativeEvent?.isComposing) {
      return
    }

    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submitMessage()
    }
  }

  function submitConfirmation(approved) { dispatch(decideConfirmation(approved)) }
  function selectExample(prompt) { if (!loading && !pendingAction && !expired) setMessage(prompt) }

  return (
    <section className="page-shell assistant-page">
      <div className="page-header assistant-page-header">
        <div className="page-header-main">
          <p className="page-eyebrow">CAREER GUIDANCE</p>
          <h1>Student assistant</h1>
          <p>
            Search jobs and events, explore details, and save opportunities
            with your approval.
          </p>
        </div>
        <button type="button" className="secondary-button" disabled={loading} onClick={() => dispatch(startNewConversation())}>New conversation</button>
        <button type="button" className="secondary-button" disabled={loading || Boolean(pendingAction) || expired || !state.conversationId}
          onClick={() => dispatch(sendChat('/compact'))}>Compact conversation</button>
        <span className="assistant-status-badge">
          <span aria-hidden="true" /> AI assistant
        </span>
      </div>

      <section className="surface-card" aria-label="Model usage">
        <p>Last completed request: prompt {state.usage?.prompt_tokens ?? 'unknown'} · completion {state.usage?.completion_tokens ?? 'unknown'} · total {state.usage?.total_tokens ?? 'unknown'} tokens · model calls {state.usage?.model_calls ?? 'unknown'}.</p>
        <p>Latest-call context: {state.usage?.context_percent == null ? 'unknown' : `${state.usage.context_percent.toFixed(1)}%`}
          {' '}of configured request capacity ({state.usage?.context_capacity ?? 'unknown'} tokens).
          {state.usage?.context_is_estimate && ' Estimated occupancy from measured prompt + completion counters; not an exact resident-window measurement.'}</p>
        <p>Request prompt totals overlap; they are not context occupancy. Missing metadata is unknown.</p>
        {contextWarning(state.usage) && <p role="alert" className="error-message">Context usage exceeds 70%. Consider /compact.</p>}
        {state.usage?.calls.map(call => <p key={call.index}>Call {call.index} ({call.purpose}, {call.source}): prompt {call.prompt_tokens ?? 'unknown'}, completion {call.completion_tokens ?? 'unknown'}.</p>)}
        {state.compaction && <p role="status">Compaction: {state.compaction.status}{state.compaction.automatic ? ' (automatic)' : ''}; before {state.compaction.before_prompt_tokens ?? 'unknown'} → after {state.compaction.after_prompt_tokens ?? 'unknown'} prompt tokens ({state.compaction.measurement_source}).</p>}
      </section>

      <div className="surface-card assistant-workspace">
        <div
          className="assistant-conversation"
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          aria-busy={loading}
          aria-label="Assistant conversation"
        >
          {conversation.length === 0 ? (
            <div className="assistant-welcome">
              <span className="assistant-welcome-mark" aria-hidden="true">
                ✦
              </span>
              <h2>How can I help with your career search?</h2>
              <p>
                Ask for real jobs, event recommendations, opportunity
                details, or help saving something for later.
              </p>
              <div className="assistant-examples" aria-label="Example prompts">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    type="button"
                    key={prompt}
                    disabled={loading || Boolean(pendingAction) || expired}
                    onClick={() => selectExample(prompt)}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="assistant-message-list">
              {conversation.map((entry, index) => (
                <article
                  className={`assistant-message assistant-message-${entry.role}`}
                  key={index}
                >
                  <span className="assistant-message-author">
                    {entry.role === 'user' ? 'You' : 'Assistant'}
                  </span>
                  <p>{entry.role === 'assistant' ? renderInline(entry.content) : entry.content}</p>
                </article>
              ))}
            </div>
          )}

          {loading && (
            <div className="assistant-typing" role="status">
              <span aria-hidden="true">•••</span>
              {pendingAction ? 'Submitting your decision' : 'Assistant is thinking'}
            </div>
          )}

          <div ref={conversationEndRef} />
        </div>

        {pendingAction && (
          <section
            className="assistant-confirmation"
            aria-labelledby="assistant-confirmation-title"
          >
            <span className="assistant-confirmation-icon" aria-hidden="true">
              ✓
            </span>
            <div className="assistant-confirmation-copy">
              <p className="page-eyebrow">CONFIRM SAVE</p>
              <h2 id="assistant-confirmation-title">
                {pendingAction.summary}
              </h2>
              <p>This action changes your saved opportunities.</p>
            </div>
            <div className="assistant-confirmation-actions">
              <button
                className="secondary-button"
                type="button"
                disabled={loading}
                onClick={() => submitConfirmation(false)}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                type="button"
                disabled={loading}
                onClick={() => submitConfirmation(true)}
              >
                Confirm
              </button>
            </div>
          </section>
        )}

        <div className="assistant-feedback" aria-live="polite">
          {error && <p className="error-message" role="alert">{error}</p>}
          <p className="visually-hidden" role="status">{statusMessage}</p>
        </div>

        <form className="assistant-composer" onSubmit={handleSubmit}>
          <label htmlFor="assistant-message">Message the assistant</label>
          <div className="assistant-composer-row">
            <textarea
              id="assistant-message"
              value={message}
              maxLength={MAX_MESSAGE_LENGTH}
              rows="3"
              placeholder={
                pendingAction
                  ? 'Resolve the pending save before sending another message.'
                  : 'Ask about jobs, events, or saved preferences...'
              }
              disabled={loading || Boolean(pendingAction) || expired}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button
              className="primary-button assistant-send-button"
              type="submit"
              disabled={!canSend}
            >
              {loading && !pendingAction ? 'Sending...' : 'Send'}
            </button>
          </div>
          <div className="assistant-composer-help">
            <span>Enter to send · Shift+Enter for a new line</span>
            <span>
              {message.length.toLocaleString()} /{' '}
              {MAX_MESSAGE_LENGTH.toLocaleString()}
            </span>
          </div>
        </form>
      </div>
    </section>
  )
}

export default AssistantPage
