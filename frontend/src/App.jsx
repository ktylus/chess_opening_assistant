import { useState, useMemo } from 'react'
import { Chess } from 'chess.js'
import Board from './components/Board'
import Chat from './components/Chat'

export default function App() {
  const [moves, setMoves] = useState([])
  const [viewIndex, setViewIndex] = useState(0)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  // Ties the turns of one chat together in the backend logs. Only the frontend
  // knows where a conversation starts, so it is minted here and reset on reset.
  const [conversationId, setConversationId] = useState(() => crypto.randomUUID())

  const currentPgn = useMemo(() => {
    const chess = new Chess()
    for (let i = 0; i < viewIndex; i++) chess.move(moves[i])
    // Throwing away the PGN headers and the trailing star char.
    return chess.pgn()
      .split('\n')
      .filter(line => !line.startsWith('['))
      .join('\n')
      .replace(/\s*\*$/, '')
      .trim()
  }, [moves, viewIndex])

  function handleMove(san) {
    const newMoves = [...moves, san]
    setMoves(newMoves)
    setViewIndex(newMoves.length)
  }

  function handleBack() {
    setViewIndex(v => Math.max(0, v - 1))
  }

  function handleForward() {
    setViewIndex(v => Math.min(moves.length, v + 1))
  }

  async function handleSend(text) {
    const userMsg = { role: 'user', content: text }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setLoading(true)

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: nextMessages,
          pgn: currentPgn,
          conversation_id: conversationId,
        }),
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''

      setMessages([...nextMessages, { role: 'assistant', content: '' }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        accumulated += decoder.decode(value, { stream: true })
        setMessages([...nextMessages, { role: 'assistant', content: accumulated }])
      }
    } catch (err) {
      setMessages([...nextMessages, { role: 'assistant', content: 'Error contacting the server.' }])
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setMoves([])
    setViewIndex(0)
    setMessages([])
    setConversationId(crypto.randomUUID())
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Chess Opening Assistant</h1>
        <button className="reset-btn" onClick={handleReset}>Reset</button>
      </header>
      <main className="app-body">
        <Board
          moves={moves}
          viewIndex={viewIndex}
          onMove={handleMove}
          onBack={handleBack}
          onForward={handleForward}
        />
        <Chat
          messages={messages}
          onSend={handleSend}
          loading={loading}
        />
      </main>
    </div>
  )
}
