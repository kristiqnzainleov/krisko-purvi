"""Чат с малкия модел.

Интерактивно:  .venv/bin/python chat.py
Еднократно:    .venv/bin/python chat.py "здрасти"
"""
import os
import sys

from model import load

TOP_P = 0.9  # свобода на отговорите; None = винаги един и същ отговор
model, tokenizer = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "model"))
# Модел с по-дълъг прозорец може да провери последния си отговор, когато му кажат, че е сгрешил.
USES_CONTEXT = model.block_size >= 256
CORRECTION_WORDS = ("греш", "бърка", "обърка", "не е вярно", "невярно", "не е така", "не си прав",
                    "не е правилно", "неправилно")


def is_correction(message: str) -> bool:
    """Казва ли човекът, че последният отговор е грешен? ("грешно е", "сбърка", "не е вярно")"""
    text = message.lower()
    return (any(word in text for word in CORRECTION_WORDS) and " ли" not in text
            and not any(ch.isdigit() for ch in text))


def reply_stream(message: str, context=None):
    """Подава отговора на парчета, докато моделът го генерира.

    context е предишната размяна (въпрос, отговор) или None. Моделът я вижда само когато
    човекът казва, че е сгрешил: <user>предишен въпрос<bot>предишен отговор<user>грешно е<bot>
    """
    prompt = []
    correcting = USES_CONTEXT and is_correction(message) and bool(context and context[0] and context[1])
    if correcting:                                     # само тогава моделът вижда предишната размяна
        before_q = tokenizer.encode(context[0].strip().lower()[:60])
        before_a = tokenizer.encode(context[1].strip()[:90])
        prompt = [tokenizer.user] + before_q + [tokenizer.bot] + before_a
    prompt += [tokenizer.user] + tokenizer.encode(message.strip().lower()[:60]) + [tokenizer.bot]
    # При сметки няма място за случайност: взима се винаги най-вероятният символ.
    is_math = any(ch.isdigit() for ch in message) or any(w in message.lower() for w in ("плюс", "минус", "делено"))
    top_p = None if is_math or correcting else TOP_P
    drafting = False      # при сметки моделът първо пише чернова в [скоби]; тя не се показва
    for token in model.stream(prompt, tokenizer.eos, top_p=top_p):
        piece = tokenizer.decode([token])
        if piece == "[":
            drafting = True
        elif piece == "]":
            drafting = False
        elif not drafting:
            yield piece


def reply(message: str, context=None) -> str:
    return "".join(reply_stream(message, context)).strip()


def main():
    if len(sys.argv) > 1:
        print(reply(" ".join(sys.argv[1:])))
    else:
        print("Пиши нещо (празен ред или Ctrl+C за изход).")
        context = None
        try:
            while True:
                msg = input("Ти: ")
                if not msg.strip():
                    break
                print("Бот: ", end="")
                answer = ""
                for piece in reply_stream(msg, context):
                    answer += piece
                    print(piece, end="", flush=True)
                print()
                context = (msg, answer)
        except (KeyboardInterrupt, EOFError):
            print()


if __name__ == "__main__":
    main()
