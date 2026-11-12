"""Собствен мъничък езиков модел – написан на ръка, само с PyTorch.

Без готови архитектури и без библиотеката Transformers: тук са токенизаторът,
вниманието (attention), слоевете, генерирането и записът на модела.
"""
import json
import math
import os

import torch
import torch.nn as nn
import torch.nn.functional as F
from safetensors.torch import load_file, save_file

SPECIAL = ["<pad>", "<user>", "<bot>", "<eos>", "<unk>"]


class CharTokenizer:
    """Всеки символ е отделен токен. Речникът идва само от нашите данни."""

    def __init__(self, chars):
        self.itos = SPECIAL + [c for c in chars if c not in SPECIAL]
        self.stoi = {s: i for i, s in enumerate(self.itos)}
        self.pad, self.user, self.bot, self.eos, self.unk = range(5)

    @classmethod
    def from_texts(cls, texts):
        return cls(sorted(set("".join(texts))))

    def encode(self, text):
        return [self.stoi.get(c, self.unk) for c in text]

    def decode(self, ids):
        return "".join(self.itos[i] for i in ids if i >= len(SPECIAL))

    def __len__(self):
        return len(self.itos)


class Attention(nn.Module):
    """Причинно самовнимание: всеки символ гледа само символите преди себе си."""

    def __init__(self, dim, heads):
        super().__init__()
        self.heads = heads
        self.qkv = nn.Linear(dim, dim * 3)
        self.out = nn.Linear(dim, dim)

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qkv(x).view(B, T, 3, self.heads, C // self.heads).permute(2, 0, 3, 1, 4)
        scores = q @ k.transpose(-2, -1) / math.sqrt(k.shape[-1])
        future = torch.triu(torch.ones(T, T, dtype=torch.bool, device=x.device), diagonal=1)
        weights = scores.masked_fill(future, float("-inf")).softmax(dim=-1)
        return self.out((weights @ v).transpose(1, 2).reshape(B, T, C))


class Block(nn.Module):
    def __init__(self, dim, heads):
        super().__init__()
        self.norm1, self.attn = nn.LayerNorm(dim), Attention(dim, heads)
        self.norm2 = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(nn.Linear(dim, dim * 4), nn.ReLU(), nn.Linear(dim * 4, dim))

    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        return x + self.mlp(self.norm2(x))


class TinyLM(nn.Module):
    def __init__(self, vocab_size, dim=64, layers=2, heads=4, block_size=128):
        super().__init__()
        self.block_size = block_size
        self.embed = nn.Embedding(vocab_size, dim)
        # Синусоидални позиции (не се учат, затова не се и записват)
        pos = torch.arange(block_size).unsqueeze(1)
        freq = torch.exp(torch.arange(0, dim, 2) * (-math.log(10000.0) / dim))
        table = torch.zeros(block_size, dim)
        table[:, 0::2], table[:, 1::2] = torch.sin(pos * freq), torch.cos(pos * freq)
        self.register_buffer("positions", table, persistent=False)
        self.blocks = nn.ModuleList(Block(dim, heads) for _ in range(layers))
        self.norm = nn.LayerNorm(dim)
        self.head = nn.Linear(dim, vocab_size)

    def forward(self, ids):
        x = self.embed(ids) * math.sqrt(self.embed.embedding_dim) + self.positions[: ids.shape[1]]
        for block in self.blocks:
            x = block(x)
        return self.head(self.norm(x))

    def loss(self, ids, targets):
        """targets са следващите символи; -100 означава "тук не се учи"."""
        logits = self(ids)
        return F.cross_entropy(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1), ignore_index=-100)

    def num_parameters(self):
        return sum(p.numel() for p in self.parameters())

    @torch.no_grad()
    def stream(self, ids, eos_id, max_new=100, top_p=None):
        """Продължава поредицата символ по символ и ги подава един по един.

        top_p=None  -> винаги най-вероятният символ (един и същ отговор всеки път).
        top_p=0.9   -> избира на случаен принцип измежду символите, които заедно носят
                       90% от вероятността. Където моделът е сигурен, нищо не се променя;
                       където знае няколко варианта на отговор, избира различен всеки път.
        """
        ids = list(ids)[-(self.block_size - 1):]
        for _ in range(max_new):
            if len(ids) >= self.block_size:
                break
            probs = self(torch.tensor([ids]))[0, -1].softmax(dim=-1)
            if top_p is None:
                next_id = int(probs.argmax())
            else:
                sorted_probs, order = probs.sort(descending=True)
                keep = sorted_probs.cumsum(0) - sorted_probs < top_p
                choice = torch.multinomial(sorted_probs * keep, 1)
                next_id = int(order[choice])
            if next_id == eos_id:
                break
            ids.append(next_id)
            yield next_id

    def generate(self, ids, eos_id, max_new=100, top_p=None):
        return list(self.stream(ids, eos_id, max_new, top_p))


def save(model, tokenizer, folder, **config):
    os.makedirs(folder, exist_ok=True)
    save_file(model.state_dict(), os.path.join(folder, "model.safetensors"))
    with open(os.path.join(folder, "config.json"), "w", encoding="utf-8") as f:
        json.dump({**config, "vocab": tokenizer.itos}, f, ensure_ascii=False, indent=1)


def load(folder):
    with open(os.path.join(folder, "config.json"), encoding="utf-8") as f:
        config = json.load(f)
    tokenizer = CharTokenizer(config.pop("vocab"))
    model = TinyLM(len(tokenizer), **config)
    model.load_state_dict(load_file(os.path.join(folder, "model.safetensors")))
    return model.eval(), tokenizer
