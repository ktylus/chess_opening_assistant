import functools
import io

import chess.pgn
import polars as pl


@functools.cache
def load_eco_code_data():
    eco_codes = pl.read_parquet(
        "hf://datasets/Lichess/chess-openings/data/train-00000-of-00001.parquet"
    ).select(pl.col("eco"), pl.col("pgn"), pl.col("epd"))
    return eco_codes


def get_eco_code(pgn: str) -> str | None:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return None

    board = game.board()
    epd_states: list[str] = []
    for move in game.mainline_moves():
        board.push(move)
        epd_states.append(board.epd())

    if not epd_states:
        return None

    eco_data = load_eco_code_data()
    eco_lookup: dict[str, str] = dict(
        zip(eco_data["epd"].to_list(), eco_data["eco"].to_list(), strict=True)
    )

    for epd in reversed(epd_states):
        if epd in eco_lookup:
            return eco_lookup[epd]

    return None
