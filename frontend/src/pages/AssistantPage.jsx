import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { selectAssistant, sendChat, decideConfirmation, startNewConversation } from '../store/assistantSlice.js'


const MAX_MESSAGE_LENGTH = 8000
const EXAMPLE_PROMPTS = [
  'Find data analyst jobs in San Jose.',
  'Show career events for data science majors.',
  'What jobs match my saved preferences?',
]

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
        <span className="assistant-status-badge">
          <span aria-hidden="true" /> AI assistant
        </span>
      </div>

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
                  <p>{entry.content}</p>
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
