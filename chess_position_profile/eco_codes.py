import io

import chess.pgn
import polars as pl


class EcoCodeLookup:
    def __init__(self):
        eco_data = pl.read_parquet(
            "hf://datasets/Lichess/chess-openings/data/train-00000-of-00001.parquet"
        ).select(pl.col("eco"), pl.col("epd"))
        self._lookup: dict[str, str] = dict(
            zip(eco_data["epd"].to_list(), eco_data["eco"].to_list(), strict=True)
        )

    def _epd_states(self, pgn: str) -> list[str]:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            return []
        board = game.board()
        states = []
        for move in game.mainline_moves():
            board.push(move)
            states.append(board.epd())
        return states

    def get(self, pgn: str) -> str | None:
        for epd in reversed(self._epd_states(pgn)):
            if epd in self._lookup:
                return self._lookup[epd]
        return None

    def get_batch(self, pgns: list[str]) -> list[str | None]:
        return [self.get(pgn) for pgn in pgns]
