import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'

export default function Chat({ messages, onSend, loading }) {
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
              <ReactMarkdown>{msg.content}</ReactMarkdown>
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
    </div>
  )
}
