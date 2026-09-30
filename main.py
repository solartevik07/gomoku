"""
main.py
Точка входу: запускає гру Gomoku (5 в ряд) проти ШІ.

Запуск:
    python3 main.py
"""

import tkinter as tk

from gui import GomokuGUI

BOARD_SIZE = 13  # стандартна дошка Gomoku — 15x15, тут 13x13 для швидшого ШІ


def main():
    root = tk.Tk()
    root.resizable(False, False)
    app = GomokuGUI(root, size=BOARD_SIZE)

    # Спочатку даємо tkinter повністю розкласти й намалювати всі віджети —
    # без цього на macOS вікно інколи показується недомальованим (порожнім),
    # якщо одразу після цього форсувати topmost/фокус.
    root.update_idletasks()
    root.update()

    # І лише тепер піднімаємо вікно на передній план та забираємо фокус —
    # на macOS вікно tkinter, запущене з IDE, інколи ховається позаду.
    # Обгорнуто в try/except: на старому/системному Tk (Apple-шний Tk 8.5,
    # /usr/bin/python3) ці виклики іноді кидають TclError навіть коли вікно
    # насправді працює нормально — тоді просто пропускаємо цей косметичний крок.
    try:
        root.lift()
        root.attributes("-topmost", True)
        root.after(200, lambda: root.attributes("-topmost", False))
        root.after(200, root.focus_force)
    except tk.TclError:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()
