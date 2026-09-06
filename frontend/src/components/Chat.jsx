import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'

// The model wraps chess notation in LaTeX-style `$...$` delimiters, which
// react-markdown leaves as literal text. Convert them to inline code instead.
function normalizeContent(content) {
  return content.replace(/\$([^$\n]+?)\$/g, '`$1`')
}

export default function Chat({ messages, onSend, loading, conversationId }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function handleSubmit(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    onSend(text)
  }

  return (
    <div className="chat-panel">
      <div className="message-list">
        {messages.length === 0 && (
          <p className="empty-hint">Ask about the current position...</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <span className="message-role">{msg.role === 'user' ? 'You' : 'Assistant'}</span>
            <div className="message-content">
              <ReactMarkdown>{normalizeContent(msg.content)}</ReactMarkdown>
            </div>
          </div>
        ))}
        {loading && messages[messages.length - 1]?.role !== 'assistant' && (
          <div className="message assistant">
            <span className="message-role">Assistant</span>
            <p className="thinking">Thinking...</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about this position..."
          disabled={loading}
          autoFocus
        />
        <button type="submit" disabled={loading || !input.trim()}>Send</button>
      </form>
      <p className="board-hint">Responses are based on the position currently on the board, not on moves described in the chat.</p>
      <details className="privacy-notice">
        <summary>Privacy and data use</summary>
        <p>
          Conversation content and agent activity are sent to LangSmith and
          retained temporarily, for no more than 30 days, so the project owner
          can review and improve this experimental assistant. Please do not
          include names, contact details, or other personal information.
        </p>
        <p>
          When you ask a question, we store a random ID in your browser and
          include it in operational logs to count active browsers, including
          failed requests. It persists across visits and chat resets until you
          clear this site's browser storage.
        </p>
        <p>
          No account is required. Operational logs exclude chat text and do not
          intentionally retain IP addresses. To request deletion, open a GitHub
          issue containing this conversation ID: <code>{conversationId}</code>.
        </p>
        <a
          href="https://github.com/ktylus/chess_opening_assistant/issues/new"
          target="_blank"
          rel="noreferrer"
        >
          Request deletion
        </a>
      </details>
    </div>
  )
}
