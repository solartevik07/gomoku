"""
gui.py
Графічний інтерфейс для Gomoku на основі tkinter (входить у стандартну
бібліотеку Python, додаткових залежностей не потрібно).

Два режими:
- "Гравець проти ШІ" — гравець (чорні) клікає по дошці, ШІ (білі) відповідає.
- "ШІ проти ШІ" — обидві сторони веде GomokuAI, можна вибрати різну
  складність для чорних і білих та спостерігати за грою.

У будь-якому режимі рахунок ходу ШІ виконується у фоновому потоці, щоб
вікно не "зависало".
"""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ai import GomokuAI
from board import Board, EMPTY, HUMAN, AI

CELL_SIZE = 38
MARGIN = 32
STONE_RADIUS = 16

# Параметри рівнів складності: глибина пошуку та ліміт часу на хід (сек.)
DIFFICULTIES = {
    "Новачок": dict(max_depth=1, time_limit=0.5, top_n_moves=6, guarantee_forcing_checks=False),
    "Легкий": dict(max_depth=2, time_limit=1.5, top_n_moves=10),
    "Середній": dict(max_depth=3, time_limit=3.0, top_n_moves=12),
    "Складний": dict(max_depth=4, time_limit=5.0, top_n_moves=14),
}

MODE_PVA = "Гравець проти ШІ"
MODE_AVA = "ШІ проти ШІ"
MODES = [MODE_PVA, MODE_AVA]

# Пауза між ходами в режимі "ШІ проти ШІ" (мс) — щоб гру було видно,
# а не миттєвий стрибок до фінальної позиції.
AUTOPLAY_DELAY_MS = 400


class GomokuGUI:
    def __init__(self, root: tk.Tk, size: int = 13):
        self.root = root
        self.root.title("Gomoku (5 в ряд) — гравець проти ШІ")
        self.size = size

        self.board = Board(size)
        self.ai: GomokuAI = None            # режим "Гравець проти ШІ"
        self.black_ai: GomokuAI = None      # режим "ШІ проти ШІ"
        self.white_ai: GomokuAI = None
        self.ai_result_queue: "queue.Queue" = queue.Queue()
        self.game_over = False
        self.ai_thinking = False    # будь-який рушій зараз рахує хід
        self.auto_running = False   # автогра ШІ-проти-ШІ триває

        self._build_top_panel()
        self._build_canvas()
        self._build_status_bar()

        self.new_game()
        self.root.update_idletasks()

    def current_mode(self) -> str:
        return self.mode_var.get()

    # ------------------------------------------------------------------
    # Побудова віджетів
    # ------------------------------------------------------------------
    def _build_top_panel(self):
        panel = tk.Frame(self.root)
        panel.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

        tk.Label(panel, text="Режим:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value=MODE_PVA)
        mode_menu = ttk.Combobox(
            panel, textvariable=self.mode_var, values=MODES,
            state="readonly", width=18
        )
        mode_menu.pack(side=tk.LEFT, padx=6)
        mode_menu.bind("<<ComboboxSelected>>", self.on_mode_change)

        self.new_game_btn = tk.Button(panel, text="Нова гра", command=self.new_game)
        self.new_game_btn.pack(side=tk.LEFT, padx=6)

        # --- Керування для режиму "Гравець проти ШІ" ---
        self.pva_frame = tk.Frame(panel)
        tk.Label(self.pva_frame, text="Складність ШІ:").pack(side=tk.LEFT)
        self.difficulty_var = tk.StringVar(value="Новачок")
        ttk.Combobox(
            self.pva_frame, textvariable=self.difficulty_var,
            values=list(DIFFICULTIES.keys()), state="readonly", width=10
        ).pack(side=tk.LEFT, padx=6)

        # --- Керування для режиму "ШІ проти ШІ" ---
        self.ava_frame = tk.Frame(panel)
        tk.Label(self.ava_frame, text="Чорні:").pack(side=tk.LEFT)
        self.black_difficulty_var = tk.StringVar(value="Легкий")
        ttk.Combobox(
            self.ava_frame, textvariable=self.black_difficulty_var,
            values=list(DIFFICULTIES.keys()), state="readonly", width=10
        ).pack(side=tk.LEFT, padx=4)

        tk.Label(self.ava_frame, text="Білі:").pack(side=tk.LEFT, padx=(10, 0))
        self.white_difficulty_var = tk.StringVar(value="Складний")
        ttk.Combobox(
            self.ava_frame, textvariable=self.white_difficulty_var,
            values=list(DIFFICULTIES.keys()), state="readonly", width=10
        ).pack(side=tk.LEFT, padx=4)

        self.start_btn = tk.Button(self.ava_frame, text="Старт", command=self.start_autoplay)
        self.start_btn.pack(side=tk.LEFT, padx=(10, 4))
        self.stop_btn = tk.Button(self.ava_frame, text="Стоп", command=self.stop_autoplay,
                                   state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        # За замовчуванням показуємо панель "Гравець проти ШІ"
        self.pva_frame.pack(side=tk.LEFT)

    def _build_canvas(self):
        canvas_size = MARGIN * 2 + CELL_SIZE * (self.size - 1)
        self.canvas = tk.Canvas(self.root, width=canvas_size, height=canvas_size, bg="#DEB887")
        self.canvas.pack(padx=8, pady=8)
        self.canvas.bind("<Button-1>", self.on_click)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Ваш хід (чорні)")
        status = tk.Label(self.root, textvariable=self.status_var, font=("Arial", 12))
        status.pack(side=tk.BOTTOM, pady=6)

    # ------------------------------------------------------------------
    # Малювання
    # ------------------------------------------------------------------
    def draw_board(self):
        self.canvas.delete("all")
        last = (self.size - 1) * CELL_SIZE + MARGIN

        for i in range(self.size):
            y = MARGIN + i * CELL_SIZE
            self.canvas.create_line(MARGIN, y, last, y)
            x = MARGIN + i * CELL_SIZE
            self.canvas.create_line(x, MARGIN, x, last)

        for r in range(self.size):
            for c in range(self.size):
                v = self.board.grid[r][c]
                if v != EMPTY:
                    self._draw_stone(r, c, v)

        if self.board.last_move:
            r, c = self.board.last_move
            x, y = self._cell_to_xy(r, c)
            self.canvas.create_oval(
                x - STONE_RADIUS - 4, y - STONE_RADIUS - 4,
                x + STONE_RADIUS + 4, y + STONE_RADIUS + 4,
                outline="red", width=2
            )

    def _draw_stone(self, r, c, player):
        x, y = self._cell_to_xy(r, c)
        color = "black" if player == HUMAN else "white"
        self.canvas.create_oval(
            x - STONE_RADIUS, y - STONE_RADIUS,
            x + STONE_RADIUS, y + STONE_RADIUS,
            fill=color, outline="black", width=2
        )

    def _cell_to_xy(self, r, c):
        return MARGIN + c * CELL_SIZE, MARGIN + r * CELL_SIZE

    def _xy_to_cell(self, x, y):
        c = round((x - MARGIN) / CELL_SIZE)
        r = round((y - MARGIN) / CELL_SIZE)
        return r, c

    # ------------------------------------------------------------------
    # Перемикання режиму
    # ------------------------------------------------------------------
    def on_mode_change(self, event=None):
        self.stop_autoplay()
        if self.current_mode() == MODE_AVA:
            self.pva_frame.pack_forget()
            self.ava_frame.pack(side=tk.LEFT)
        else:
            self.ava_frame.pack_forget()
            self.pva_frame.pack(side=tk.LEFT)
        self.new_game()

    # ------------------------------------------------------------------
    # Логіка гри
    # ------------------------------------------------------------------
    def new_game(self):
        if self.ai_thinking:
            return  # захист від гонки потоків: не можна почати нову гру, поки рахує ШІ

        self.stop_autoplay()
        self.board = Board(self.size)
        self.game_over = False

        if self.current_mode() == MODE_AVA:
            black_params = DIFFICULTIES[self.black_difficulty_var.get()]
            white_params = DIFFICULTIES[self.white_difficulty_var.get()]
            # GomokuAI не "знає", що він саме ШІ, а не людина — параметр
            # player лише каже, яким значенням на дошці він грає, тому той
            # самий клас однаково добре керує будь-якою стороною.
            self.black_ai = GomokuAI(player=HUMAN, **black_params)
            self.white_ai = GomokuAI(player=AI, **white_params)
            self.status_var.set('Натисніть "Старт", щоб почати гру ШІ проти ШІ')
        else:
            params = DIFFICULTIES[self.difficulty_var.get()]
            self.ai = GomokuAI(player=AI, **params)
            self.status_var.set("Ваш хід (чорні)")

        self.draw_board()

    # --- Режим "Гравець проти ШІ" ---
    def on_click(self, event):
        if self.current_mode() != MODE_PVA or self.game_over or self.ai_thinking:
            return

        r, c = self._xy_to_cell(event.x, event.y)
        if not self.board.in_bounds(r, c) or not self.board.is_empty(r, c):
            return

        self.board.make_move(r, c, HUMAN)
        self.draw_board()

        if self.board.check_win(r, c):
            self.end_game("Ви перемогли! 🎉")
            return
        if self.board.is_full():
            self.end_game("Нічия!")
            return

        self._start_ai_turn()

    def _start_ai_turn(self):
        self.status_var.set("ШІ думає...")
        self.ai_thinking = True
        self.new_game_btn.config(state=tk.DISABLED)
        thread = threading.Thread(target=self._ai_worker, daemon=True)
        thread.start()
        self.root.after(100, self._check_ai_result)

    def _ai_worker(self):
        move = self.ai.choose_move(self.board)
        self.ai_result_queue.put(move)

    def _check_ai_result(self):
        try:
            move = self.ai_result_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._check_ai_result)
            return

        self.ai_thinking = False
        self.new_game_btn.config(state=tk.NORMAL)

        if move is None:
            self.end_game("Нічия!")
            return

        r, c = move
        self.board.make_move(r, c, AI)
        self.draw_board()

        if self.board.check_win(r, c):
            self.end_game("ШІ переміг. Спробуйте ще раз!")
            return
        if self.board.is_full():
            self.end_game("Нічия!")
            return

        self.status_var.set("Ваш хід (чорні)")

    # --- Режим "ШІ проти ШІ" ---
    def start_autoplay(self):
        if self.current_mode() != MODE_AVA or self.game_over or self.auto_running:
            return
        self.auto_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.new_game_btn.config(state=tk.DISABLED)
        self._play_next_ai_move()

    def stop_autoplay(self):
        self.auto_running = False
        if hasattr(self, "start_btn"):
            is_ava = self.current_mode() == MODE_AVA
            self.start_btn.config(state=(tk.NORMAL if is_ava and not self.game_over else tk.DISABLED))
            self.stop_btn.config(state=tk.DISABLED)
        if hasattr(self, "new_game_btn") and not self.ai_thinking:
            self.new_game_btn.config(state=tk.NORMAL)

    def _play_next_ai_move(self):
        if not self.auto_running or self.game_over:
            return

        # Чорні (HUMAN-значення на дошці) завжди ходять першими, тобто
        # парна кількість зроблених ходів означає, що зараз хід чорних.
        black_turn = len(self.board.move_history) % 2 == 0
        engine = self.black_ai if black_turn else self.white_ai
        mover = HUMAN if black_turn else AI

        self.status_var.set(("Чорні" if black_turn else "Білі") + " думають...")
        self.ai_thinking = True
        thread = threading.Thread(target=self._ai_vs_ai_worker, args=(engine,), daemon=True)
        thread.start()
        self.root.after(100, lambda: self._check_ai_vs_ai_result(mover))

    def _ai_vs_ai_worker(self, engine: GomokuAI):
        move = engine.choose_move(self.board)
        self.ai_result_queue.put(move)

    def _check_ai_vs_ai_result(self, mover: int):
        try:
            move = self.ai_result_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, lambda: self._check_ai_vs_ai_result(mover))
            return

        self.ai_thinking = False

        if move is None:
            self.end_game("Нічия!")
            return

        r, c = move
        self.board.make_move(r, c, mover)
        self.draw_board()

        if self.board.check_win(r, c):
            winner = "Чорні" if mover == HUMAN else "Білі"
            self.end_game(f"{winner} перемогли!")
            return
        if self.board.is_full():
            self.end_game("Нічия!")
            return

        if self.auto_running:
            self.root.after(AUTOPLAY_DELAY_MS, self._play_next_ai_move)

    # ------------------------------------------------------------------
    def end_game(self, message: str):
        self.game_over = True
        self.auto_running = False
        self.new_game_btn.config(state=tk.NORMAL)
        if self.current_mode() == MODE_AVA:
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set(message)
        messagebox.showinfo("Гра закінчена", message)
