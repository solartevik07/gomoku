"""
board.py
Логіка ігрового поля для Gomoku (5 в ряд).

Клас Board відповідає лише за стан дошки та базові операції над нею:
розміщення каменів, скасування ходу, перевірку виграшу та генерацію
"кандидатів" на наступний хід (клітин поблизу вже зайнятих).
"""

from typing import List, Optional, Tuple

EMPTY = 0
HUMAN = 1  # чорні, ходять першими
AI = 2     # білі

WIN_LENGTH = 5

# 4 напрямки для перевірки ліній: →, ↓, ↘, ↙
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]


class Board:
    def __init__(self, size: int = 13):
        self.size = size
        self.grid: List[List[int]] = [[EMPTY] * size for _ in range(size)]
        self.move_history: List[Tuple[int, int]] = []
        self.last_move: Optional[Tuple[int, int]] = None

        # Обмежувальна рамка навколо вже зроблених ходів.
        # Використовується, щоб не сканувати всю дошку під час оцінки позиції.
        self.min_r: Optional[int] = None
        self.max_r: Optional[int] = None
        self.min_c: Optional[int] = None
        self.max_c: Optional[int] = None
        self._bounds_stack: List[Tuple] = []

    # ------------------------------------------------------------------
    # Базові операції
    # ------------------------------------------------------------------
    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def is_empty(self, r: int, c: int) -> bool:
        return self.grid[r][c] == EMPTY

    def make_move(self, r: int, c: int, player: int) -> bool:
        if not self.in_bounds(r, c) or not self.is_empty(r, c):
            return False

        self.grid[r][c] = player
        self.move_history.append((r, c))
        self.last_move = (r, c)

        self._bounds_stack.append((self.min_r, self.max_r, self.min_c, self.max_c))
        self.min_r = r if self.min_r is None else min(self.min_r, r)
        self.max_r = r if self.max_r is None else max(self.max_r, r)
        self.min_c = c if self.min_c is None else min(self.min_c, c)
        self.max_c = c if self.max_c is None else max(self.max_c, c)
        return True

    def undo_move(self) -> None:
        if not self.move_history:
            return
        r, c = self.move_history.pop()
        self.grid[r][c] = EMPTY
        self.last_move = self.move_history[-1] if self.move_history else None
        self.min_r, self.max_r, self.min_c, self.max_c = self._bounds_stack.pop()

    def is_full(self) -> bool:
        return len(self.move_history) == self.size * self.size

    # ------------------------------------------------------------------
    # Перевірка виграшу
    # ------------------------------------------------------------------
    def check_win(self, r: int, c: int) -> bool:
        """Перевіряє, чи хід (r, c) створює лінію з WIN_LENGTH+ каменів.

        Перевіряються лише лінії, що проходять через саме цю клітину —
        цього достатньо, бо виграшна лінія завжди містить останній хід.
        """
        player = self.grid[r][c]
        if player == EMPTY:
            return False

        for dr, dc in DIRECTIONS:
            count = 1
            for sign in (1, -1):
                rr, cc = r + dr * sign, c + dc * sign
                while self.in_bounds(rr, cc) and self.grid[rr][cc] == player:
                    count += 1
                    rr += dr * sign
                    cc += dc * sign
            if count >= WIN_LENGTH:
                return True
        return False

    def winner(self) -> Optional[int]:
        if self.last_move is None:
            return None
        r, c = self.last_move
        return self.grid[r][c] if self.check_win(r, c) else None

    # ------------------------------------------------------------------
    # Генерація кандидатів на хід (обмеження branching factor)
    # ------------------------------------------------------------------
    def get_candidate_moves(self, radius: int = 2) -> List[Tuple[int, int]]:
        """Повертає порожні клітини поблизу вже зайнятих.

        Без цього обмеження на дошці 13x13 довелося б розглядати до 169
        варіантів ходу на кожному рівні дерева пошуку — це занадто багато
        для minimax навіть з альфа-бета відсіканням.
        """
        if not self.move_history:
            center = self.size // 2
            return [(center, center)]

        candidates = set()
        for (r, c) in self.move_history:
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    rr, cc = r + dr, c + dc
                    if self.in_bounds(rr, cc) and self.grid[rr][cc] == EMPTY:
                        candidates.add((rr, cc))
        return list(candidates)

    def copy(self) -> "Board":
        new_board = Board(self.size)
        new_board.grid = [row[:] for row in self.grid]
        new_board.move_history = self.move_history[:]
        new_board.last_move = self.last_move
        new_board.min_r, new_board.max_r = self.min_r, self.max_r
        new_board.min_c, new_board.max_c = self.min_c, self.max_c
        return new_board
