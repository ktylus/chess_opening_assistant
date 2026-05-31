import { useMemo } from 'react'
import { Chess } from 'chess.js'
import { Chessboard } from 'react-chessboard'

export default function Board({ moves, viewIndex, onMove, onBack, onForward }) {
  const isAtEnd = viewIndex === moves.length
  const isAtStart = viewIndex === 0

  const fen = useMemo(() => {
    const chess = new Chess()
    for (let i = 0; i < viewIndex; i++) chess.move(moves[i])
    return chess.fen()
  }, [moves, viewIndex])

  function onDrop(sourceSquare, targetSquare) {
    if (!isAtEnd) return false
    const chess = new Chess()
    moves.forEach(m => chess.move(m))
    const move = chess.move({ from: sourceSquare, to: targetSquare, promotion: 'q' })
    if (!move) return false
    onMove(move.san)
    return true
  }

  const moveLabels = moves.map((san, i) => {
    const label = i % 2 === 0 ? `${Math.floor(i / 2) + 1}. ${san}` : san
    return { san, label, ply: i + 1 }
  })

  return (
    <div className="board-panel">
      <Chessboard
        position={fen}
        onPieceDrop={onDrop}
        arePiecesDraggable={isAtEnd}
        boardWidth={480}
      />

      <div className="move-list">
        <span className={viewIndex === 0 ? 'move-token active' : 'move-token'}>start</span>
        {moveLabels.map(({ san, label, ply }) => (
          <span
            key={ply}
            className={viewIndex === ply ? 'move-token active' : 'move-token'}
          >
            {label}
          </span>
        ))}
      </div>

      <div className="board-controls">
        <button onClick={onBack} disabled={isAtStart}>&#8592; Back</button>
        <button onClick={onForward} disabled={isAtEnd}>Forward &#8594;</button>
      </div>
    </div>
  )
}
