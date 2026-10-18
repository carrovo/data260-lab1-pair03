import { useState } from "react";

import api from "../../services/api";
import ErrorMessage from "../../components/ErrorMessage";

export default function Assistant() {
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [studentId, setStudentId] = useState("");
  const [autoApprove, setAutoApprove] = useState(false);
  const [showTesting, setShowTesting] = useState(false);

  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [toolCalls, setToolCalls] = useState(0);

  const suggestedPrompts = [
    "Find data science internships in San Jose",
    "Show me upcoming computer science events",
    "Find remote analytics internships",
    "What recruiting events are coming up next month?",
  ];

  const sendMessage = async (text = message) => {
    const cleanMessage = text.trim();

    if (!cleanMessage || sending) {
      return;
    }

    const userMessage = {
      role: "user",
      content: cleanMessage,
    };

    const nextConversation = [...messages, userMessage];

    setMessages(nextConversation);
    setMessage("");
    setSending(true);
    setError(null);

    try {
      const response = await api.post("/assistant/chat", {
        message: cleanMessage,

        student_id: studentId
          ? Number(studentId)
          : null,

        conversation: messages.map((item) => ({
          role: item.role,
          content: item.content,
        })),

        auto_approve: autoApprove,
      });

      const assistantMessage = {
        role: "assistant",
        content:
          response.data.reply ||
          "I completed the request, but no response text was returned.",
      };

      setMessages((prev) => [...prev, assistantMessage]);

      setToolCalls(response.data.tool_calls || 0);
    } catch (err) {
      setError(err);
    } finally {
      setSending(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage();
  };

  const clearConversation = () => {
    setMessages([]);
    setToolCalls(0);
    setError(null);
  };

  return (
    <div className="dashboard-page">
      <div className="page-header assistant-page-header">
        <div className="page-header-main">
          <p className="page-eyebrow">AI RECRUITING ASSISTANT</p>

          <h1>Recruiting Assistant</h1>

          <p>
            Search opportunities and events using natural language while
            keeping the conversation context across follow-up questions.
          </p>
        </div>

        <div className="assistant-header-actions">
          {messages.length > 0 && (
            <button
              type="button"
              className="secondary-action-button"
              onClick={clearConversation}
            >
              Clear conversation
            </button>
          )}

          <button
            type="button"
            className="secondary-action-button"
            onClick={() => setShowTesting((prev) => !prev)}
          >
            {showTesting ? "Hide testing options" : "Testing options"}
          </button>
        </div>
      </div>

      <ErrorMessage error={error} />

      {showTesting && (
        <div className="dashboard-card assistant-testing-panel">
          <div>
            <strong>Testing options</strong>
            <p>
              These controls are for Lab 1 verification and can be hidden
              during the demo.
            </p>
          </div>

          <div className="assistant-testing-controls">
            <label>
              Student ID
              <input
                type="number"
                min="1"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="e.g. 1"
              />
            </label>

            <label className="assistant-checkbox">
              <input
                type="checkbox"
                checked={autoApprove}
                onChange={(e) => setAutoApprove(e.target.checked)}
              />

              <span>Auto-approve save actions</span>
            </label>
          </div>
        </div>
      )}

      <div className="assistant-layout">
        <aside className="dashboard-card assistant-sidebar">
          <div className="assistant-profile">
            <div className="assistant-avatar">AI</div>

            <div>
              <h2>Handshake Assistant</h2>
              <span className="assistant-online-status">
                <span />
                Ready
              </span>
            </div>
          </div>

          <p className="assistant-sidebar-description">
            Ask about internships, jobs, recruiting events, or refine an
            earlier search using follow-up questions.
          </p>

          <div className="assistant-capabilities">
            <div>
              <span>✓</span>
              Search jobs
            </div>

            <div>
              <span>✓</span>
              Find recruiting events
            </div>

            <div>
              <span>✓</span>
              Use conversation history
            </div>

            <div>
              <span>✓</span>
              Call verified tools
            </div>
          </div>

          <div className="assistant-stat">
            <span>Tool calls in last response</span>
            <strong>{toolCalls}</strong>
          </div>
        </aside>

        <section className="dashboard-card assistant-chat-card">
          <div className="assistant-chat-header">
            <div>
              <h2>Conversation</h2>
              <p>
                Ask a question or choose one of the suggestions below.
              </p>
            </div>
          </div>

          <div className="assistant-chat-window">
            {messages.length === 0 ? (
              <div className="assistant-welcome">
                <div className="assistant-welcome-icon">✦</div>

                <h2>How can I help?</h2>

                <p>
                  Try asking about internships, events, or opportunities
                  that match a student's interests.
                </p>

                <div className="assistant-suggestion-grid">
                  {suggestedPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="assistant-suggestion"
                      onClick={() => sendMessage(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="assistant-messages">
                {messages.map((item, index) => (
                  <div
                    key={`${item.role}-${index}`}
                    className={`assistant-message-row ${
                      item.role === "user"
                        ? "assistant-message-user"
                        : "assistant-message-ai"
                    }`}
                  >
                    {item.role === "assistant" && (
                      <div className="assistant-message-avatar">
                        AI
                      </div>
                    )}

                    <div className="assistant-message-content">
                      <span className="assistant-message-label">
                        {item.role === "user"
                          ? "You"
                          : "Assistant"}
                      </span>

                      <div className="assistant-message-bubble">
                        {item.content}
                      </div>
                    </div>
                  </div>
                ))}

                {sending && (
                  <div className="assistant-message-row assistant-message-ai">
                    <div className="assistant-message-avatar">
                      AI
                    </div>

                    <div className="assistant-message-content">
                      <span className="assistant-message-label">
                        Assistant
                      </span>

                      <div className="assistant-message-bubble assistant-thinking">
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <form
            className="assistant-composer"
            onSubmit={handleSubmit}
          >
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ask about jobs, internships, or recruiting events..."
              disabled={sending}
            />

            <button
              type="submit"
              className="primary-action-button assistant-send-button"
              disabled={!message.trim() || sending}
            >
              {sending ? "Sending..." : "Send"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}