"""Чат с малкия модел.

Интерактивно:  .venv/bin/python chat.py
Еднократно:    .venv/bin/python chat.py "здрасти"
"""
import os
import sys

from model import load

TOP_P = 0.9  # свобода на отговорите; None = винаги един и същ отговор
model, tokenizer = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "model"))
# Контекст се подава само на модел, обучен с него (такъв модел има по-дълъг прозорец).
USES_CONTEXT = model.block_size >= 256


def reply_stream(message: str, context=None):
    """Подава отговора на парчета, докато моделът го генерира.

    context е предишната размяна (въпрос, отговор) или None. Така моделът вижда
    за какво е ставало дума: <user>предишен въпрос<bot>предишен отговор<user>въпрос<bot>
    """
    prompt = []
    if USES_CONTEXT and context and context[0] and context[1]:
        before_q = tokenizer.encode(context[0].strip().lower()[:60])
        before_a = tokenizer.encode(context[1].strip()[:70])
        prompt = [tokenizer.user] + before_q + [tokenizer.bot] + before_a
    prompt += [tokenizer.user] + tokenizer.encode(message.strip().lower()[:60]) + [tokenizer.bot]
    for token in model.stream(prompt, tokenizer.eos, top_p=TOP_P):
        yield tokenizer.decode([token])


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
