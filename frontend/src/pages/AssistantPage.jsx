import { useEffect, useRef, useState } from 'react'
import { sendAssistantMessage } from '../api'
import useAuth from '../auth/useAuth'


const MAX_MESSAGE_LENGTH = 8000
const MAX_CONVERSATION_MESSAGES = 40
const EXAMPLE_PROMPTS = [
  'Find data analyst jobs in San Jose.',
  'Show career events for data science majors.',
  'What jobs match my saved preferences?',
]

function validatedConversation(messages) {
  if (!Array.isArray(messages)) {
    return []
  }

  return messages
    .filter((message) =>
      (message?.role === 'user' || message?.role === 'assistant') &&
      typeof message.content === 'string' &&
      message.content.trim(),
    )
    .map((message) => ({
      role: message.role,
      content: message.content.trim().slice(0, MAX_MESSAGE_LENGTH),
    }))
    .slice(-MAX_CONVERSATION_MESSAGES)
}

function conversationWithKeys(messages, previousMessages, createKey) {
  const availableKeys = new Map()

  previousMessages.forEach((message) => {
    if (!message.clientKey) {
      return
    }

    const signature = `${message.role}\u0000${message.content}`
    const keys = availableKeys.get(signature) || []

    keys.push(message.clientKey)
    availableKeys.set(signature, keys)
  })

  return validatedConversation(messages).map((message) => {
    const signature = `${message.role}\u0000${message.content}`
    const keys = availableKeys.get(signature)

    return {
      ...message,
      clientKey: keys?.shift() || createKey(),
    }
  })
}

function assistantErrorMessage(requestError, isConfirmation) {
  if (!requestError.status) {
    return isConfirmation
      ? 'Unable to reach the assistant to submit your decision.'
      : 'Unable to reach the assistant. Check your connection and try again.'
  }

  switch (requestError.status) {
    case 400:
      return requestError.message || 'This confirmation is no longer valid.'
    case 401:
      return 'Your session has expired. Please sign in again.'
    case 404:
      return 'The assistant service could not find the requested resource.'
    case 409:
      return requestError.message || 'This action has already been resolved.'
    case 422:
      return requestError.message || 'The assistant request was not valid.'
    case 500:
      return 'The assistant is temporarily unavailable. Please try again.'
    default:
      return isConfirmation
        ? 'Unable to submit your decision. Please try again.'
        : 'Unable to complete the assistant request. Please try again.'
  }
}

function AssistantPage() {
  const { accessToken, logout } = useAuth()
  const [conversation, setConversation] = useState([])
  const [message, setMessage] = useState('')
  const [pendingAction, setPendingAction] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const requestInFlightRef = useRef(false)
  const conversationEndRef = useRef(null)
  const nextMessageKeyRef = useRef(0)

  function createMessageKey() {
    nextMessageKeyRef.current += 1
    return `assistant-message-${nextMessageKeyRef.current}`
  }

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
    })
  }, [conversation, pendingAction])

  const trimmedMessage = message.trim()
  const canSend = Boolean(
    trimmedMessage &&
    trimmedMessage.length <= MAX_MESSAGE_LENGTH &&
    !loading &&
    !pendingAction,
  )

  async function submitMessage() {
    if (!canSend || requestInFlightRef.current) {
      return
    }

    requestInFlightRef.current = true
    setLoading(true)
    setError('')
    setStatusMessage('Sending your message...')

    const priorConversation = validatedConversation(conversation)
    const optimisticConversation = conversationWithKeys(
      [
        ...priorConversation,
        { role: 'user', content: trimmedMessage },
      ],
      conversation,
      createMessageKey,
    )

    setConversation(optimisticConversation)
    setMessage('')

    try {
      const response = await sendAssistantMessage(
        {
          message: trimmedMessage,
          conversation: priorConversation,
        },
        accessToken,
      )
      const responseConversation = validatedConversation(
        response.conversation,
      )

      const canonicalConversation =
        responseConversation.length > 0
          ? responseConversation
          : validatedConversation([
              ...optimisticConversation,
              { role: 'assistant', content: response.reply },
            ])

      setConversation((currentConversation) =>
        conversationWithKeys(
          canonicalConversation,
          currentConversation,
          createMessageKey,
        ),
      )
      setPendingAction(response.pending_action || null)
      setStatusMessage(
        response.pending_action
          ? 'The assistant needs your confirmation before saving.'
          : 'The assistant has responded.',
      )
    } catch (requestError) {
      setError(assistantErrorMessage(requestError, false))
      setStatusMessage('The message could not be completed.')

      if (requestError.status === 401) {
        logout()
      }
    } finally {
      requestInFlightRef.current = false
      setLoading(false)
    }
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

  async function submitConfirmation(approved) {
    if (!pendingAction || loading || requestInFlightRef.current) {
      return
    }

    requestInFlightRef.current = true
    setLoading(true)
    setError('')
    setStatusMessage(
      approved ? 'Confirming this save...' : 'Cancelling this save...',
    )

    const actionToken = pendingAction.action_token

    try {
      const response = await sendAssistantMessage(
        {
          conversation: validatedConversation(conversation),
          confirmation: {
            action_token: actionToken,
            approved,
          },
        },
        accessToken,
      )

      const responseConversation = validatedConversation(
        response.conversation,
      )

      const canonicalConversation =
        responseConversation.length > 0
          ? responseConversation
          : validatedConversation([
              ...conversation,
              { role: 'assistant', content: response.reply },
            ])

      setConversation((currentConversation) =>
        conversationWithKeys(
          canonicalConversation,
          currentConversation,
          createMessageKey,
        ),
      )
      setPendingAction(null)
      setStatusMessage(
        approved ? 'Save decision completed.' : 'Save cancelled.',
      )
    } catch (requestError) {
      setError(assistantErrorMessage(requestError, true))
      setStatusMessage('The confirmation decision could not be completed.')

      if (requestError.status === 401) {
        setPendingAction(null)
        logout()
      } else if (
        requestError.status === 400 ||
        requestError.status === 409 ||
        requestError.status === 422
      ) {
        setPendingAction(null)
      }
    } finally {
      requestInFlightRef.current = false
      setLoading(false)
    }
  }

  function selectExample(prompt) {
    if (!loading && !pendingAction) {
      setMessage(prompt)
      setError('')
    }
  }

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
                    disabled={loading || Boolean(pendingAction)}
                    onClick={() => selectExample(prompt)}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="assistant-message-list">
              {conversation.map((entry) => (
                <article
                  className={`assistant-message assistant-message-${entry.role}`}
                  key={entry.clientKey}
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
              disabled={loading || Boolean(pendingAction)}
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
