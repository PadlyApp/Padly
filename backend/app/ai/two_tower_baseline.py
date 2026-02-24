"""
Padly Two-Tower recommender -- softmax baseline.

Each tower maps its raw features into a shared embedding space.
The dot product of the two embeddings becomes a 2-class logit
[no-match, match] and is trained with softmax (sparse categorical
cross-entropy).

Run from backend/:
  python -m app.ai.two_tower_baseline
  python -m app.ai.two_tower_baseline --epochs 15 --embedding-dim 128
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


def build_tower(input_dim: int, embedding_dim: int, dropout: float, name: str) -> keras.Model:
    """Single tower: raw features -> L2-normalised embedding."""
    inp = keras.Input(shape=(input_dim,), name=f"{name}_input")
    x = layers.Dense(256, activation="relu", name=f"{name}_dense1")(inp)
    x = layers.Dropout(dropout, name=f"{name}_drop1")(x)
    x = layers.Dense(128, activation="relu", name=f"{name}_dense2")(x)
    x = layers.Dense(embedding_dim, name=f"{name}_embed")(x)
    x = layers.Lambda(lambda t: tf.math.l2_normalize(t, axis=1), name=f"{name}_norm")(x)
    return keras.Model(inp, x, name=f"{name}_tower")


def build_model(user_dim: int, item_dim: int, embedding_dim: int, dropout: float) -> keras.Model:
    """Two towers + dot-product scoring with 2-class softmax output."""
    user_input = keras.Input(shape=(user_dim,), name="user_features")
    item_input = keras.Input(shape=(item_dim,), name="item_features")

    user_tower = build_tower(user_dim, embedding_dim, dropout, "user")
    item_tower = build_tower(item_dim, embedding_dim, dropout, "item")

    user_vec = user_tower(user_input)
    item_vec = item_tower(item_input)

    # dot product -> scalar similarity per sample
    dot = layers.Dot(axes=1, name="dot")([user_vec, item_vec])

    # 2-class logits: column 0 = "no match", column 1 = "match"
    # A single learned bias-free projection from 1-D dot to 2-D logits
    logits = layers.Dense(2, use_bias=False, name="logits")(dot)

    return keras.Model(
        inputs={"user_features": user_input, "item_features": item_input},
        outputs=logits,
        name="padly_two_tower",
    )


def load_data(path: Path):
    """Load the npz produced by generate_renter_data.py."""
    data = np.load(path)
    for key in ("user_features", "item_features", "labels"):
        if key not in data:
            raise ValueError(f"Missing '{key}' in {path}")

    uf = data["user_features"].astype(np.float32)
    itf = data["item_features"].astype(np.float32)
    labels = data["labels"].astype(np.int32).reshape(-1)
    return uf, itf, labels


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train Padly Two-Tower (softmax)")
    p.add_argument("--npz-path", type=Path,
                   default=Path("app/ai/dataset/train_pairs.npz"))
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--embedding-dim", type=int, default=64)
    p.add_argument("--dropout", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output-model", type=Path,
                   default=Path("app/ai/artifacts/two_tower_baseline.keras"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    tf.keras.utils.set_random_seed(args.seed)

    print(f"Loading data from {args.npz_path} ...")
    user_features, item_features, labels = load_data(args.npz_path)
    user_dim = user_features.shape[1]
    item_dim = item_features.shape[1]
    print(f"  samples: {len(labels):,}   user_dim: {user_dim}   item_dim: {item_dim}")
    print(f"  positives: {labels.sum():,}   negatives: {(labels == 0).sum():,}")

    split = int(0.8 * len(labels))
    train_x = {"user_features": user_features[:split],
                "item_features": item_features[:split]}
    val_x   = {"user_features": user_features[split:],
                "item_features": item_features[split:]}
    train_y = labels[:split]
    val_y   = labels[split:]

    model = build_model(user_dim, item_dim, args.embedding_dim, args.dropout)
    model.summary()

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=args.lr),
        loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=[keras.metrics.SparseCategoricalAccuracy(name="acc")],
    )

    model.fit(
        train_x, train_y,
        validation_data=(val_x, val_y),
        epochs=args.epochs,
        batch_size=args.batch_size,
        verbose=2,
    )

    args.output_model.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.output_model)
    print(f"\nSaved model -> {args.output_model}")


if __name__ == "__main__":
    main()
