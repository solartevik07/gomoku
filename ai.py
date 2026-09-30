import time
from typing import List, Optional, Tuple

from board import Board, EMPTY, HUMAN, AI, WIN_LENGTH

WINDOW_SCORE = {0: 0, 1: 1, 2: 10, 3: 100, 4: 10_000, 5: 1_000_000}

DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]

WIN_SCORE = 10_000_000


class TimeUp(Exception):
    """internal timelimit"""


class GomokuAI:
    def __init__(self, player: int = AI, max_depth: int = 3, time_limit: float = 3.0,
                 top_n_moves: int = 12, guarantee_forcing_checks: bool = True):
        self.player = player
        self.opponent = HUMAN if player == AI else AI
        self.max_depth = max_depth
        self.time_limit = time_limit
        self.top_n_moves = top_n_moves
        self.guarantee_forcing_checks = guarantee_forcing_checks
        self._deadline = 0.0

    def choose_move(self, board: Board) -> Optional[Tuple[int, int]]:
        candidates = board.get_candidate_moves()
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        if self.guarantee_forcing_checks:
            # Швидка перевірка: чи є хід, що виграє одразу?
            immediate = self._find_immediate_win(board, self.player)
            if immediate:
                return immediate
            # Якщо супротивник виграє наступним ходом — обов'язково блокуємо.
            block = self._find_immediate_win(board, self.opponent)
            if block:
                return block

        self._deadline = time.time() + self.time_limit
        best_move = candidates[0]

        depth = 1
        while depth <= self.max_depth:
            try:
                move, _ = self._search_root(board, depth)
                if move is not None:
                    best_move = move
            except TimeUp:
                break
            if time.time() > self._deadline:
                break
            depth += 1

        return best_move

    def _find_immediate_win(self, board: Board, player: int) -> Optional[Tuple[int, int]]:
        for (r, c) in board.get_candidate_moves():
            board.make_move(r, c, player)
            win = board.check_win(r, c)
            board.undo_move()
            if win:
                return (r, c)
        return None

    #minimax + альфа бета
    def _search_root(self, board: Board, depth: int):
        candidates = self._ordered_moves(board, self.player)
        best_score = -float("inf")
        best_move = None
        alpha, beta = -float("inf"), float("inf")

        for (r, c) in candidates:
            if time.time() > self._deadline:
                raise TimeUp

            score = self._move_score(board, r, c, self.player, depth, alpha, beta, False)
            if score > best_score:
                best_score = score
                best_move = (r, c)
            alpha = max(alpha, best_score)

        return best_move, best_score

    def _move_score(self, board: Board, r: int, c: int, player: int, depth: int,
                     alpha: float, beta: float, next_maximizing: bool) -> float:
        board.make_move(r, c, player)
        if board.check_win(r, c):
            raw = WIN_SCORE + depth
            score = raw if player == self.player else -raw
        else:
            score = self._minimax(board, depth - 1, alpha, beta, next_maximizing)
        board.undo_move()
        return score

    def _minimax(self, board: Board, depth: int, alpha: float, beta: float,
                 maximizing: bool) -> float:
        if time.time() > self._deadline:
            raise TimeUp

        current_player = self.player if maximizing else self.opponent

        if depth == 0 or board.is_full():
            return self.evaluate(board)

        candidates = self._ordered_moves(board, current_player)
        if not candidates:
            return self.evaluate(board)

        if maximizing:
            value = -float("inf")
            for (r, c) in candidates:
                score = self._move_score(board, r, c, current_player, depth, alpha, beta, False)
                value = max(value, score)
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = float("inf")
            for (r, c) in candidates:
                score = self._move_score(board, r, c, current_player, depth, alpha, beta, True)
                value = min(value, score)
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value

    def _ordered_moves(self, board: Board, player: int) -> List[Tuple[int, int]]:
        candidates = board.get_candidate_moves()
        opponent = HUMAN if player == AI else AI

        scored = [
            (self._quick_score(board, r, c, player) + self._quick_score(board, r, c, opponent), (r, c))
            for (r, c) in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[: self.top_n_moves]]

    def _quick_score(self, board: Board, r: int, c: int, player: int) -> int:
        total = 0
        for dr, dc in DIRECTIONS:
            for offset in range(-4, 1):
                cells = [(r + (offset + i) * dr, c + (offset + i) * dc) for i in range(5)]
                if all(board.in_bounds(rr, cc) for rr, cc in cells):
                    values = [player if (rr, cc) == (r, c) else board.grid[rr][cc] for rr, cc in cells]
                    total += self._window_value(values, player)
        return total

    def _window_value(self, values: List[int], player: int) -> int:
        opponent = HUMAN if player == AI else AI
        if opponent in values:
            return 0
        count = values.count(player)
        return WINDOW_SCORE.get(count, 0)

    def evaluate(self, board: Board) -> float:
        my_score = self._evaluate_player(board, self.player)
        opp_score = self._evaluate_player(board, self.opponent)
        return my_score - opp_score

    def _evaluate_player(self, board: Board, player: int) -> int:
        if board.min_r is None:
            return 0

        margin = WIN_LENGTH - 1
        r0 = max(0, board.min_r - margin)
        r1 = min(board.size - 1, board.max_r + margin)
        c0 = max(0, board.min_c - margin)
        c1 = min(board.size - 1, board.max_c + margin)

        total = 0
        grid = board.grid
        for window in self._windows_in_box(r0, r1, c0, c1):
            values = [grid[r][c] for r, c in window]
            total += self._window_value(values, player)
        return total

    @staticmethod
    def _windows_in_box(r0: int, r1: int, c0: int, c1: int):
        #горизонтальні
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 - WIN_LENGTH + 2):
                yield [(r, c + k) for k in range(WIN_LENGTH)]
        #вертикальні
        for c in range(c0, c1 + 1):
            for r in range(r0, r1 - WIN_LENGTH + 2):
                yield [(r + k, c) for k in range(WIN_LENGTH)]
        #діагональ право
        for r in range(r0, r1 - WIN_LENGTH + 2):
            for c in range(c0, c1 - WIN_LENGTH + 2):
                yield [(r + k, c + k) for k in range(WIN_LENGTH)]
        #діагональ ліво
        for r in range(r0, r1 - WIN_LENGTH + 2):
            for c in range(c0 + WIN_LENGTH - 1, c1 + 1):
                yield [(r + k, c - k) for k in range(WIN_LENGTH)]
