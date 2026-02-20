"""
Minimal TensorFlow Two-Tower baseline for Padly.

Usage examples:
  python -m app.ai.two_tower_baseline --epochs 5 --loss binary_crossentropy
  python -m app.ai.two_tower_baseline --npz-path ./data/train_data.npz --loss softmax
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


def build_model(
    user_dim: int,
    item_dim: int,
    embedding_dim: int,
    dropout: float,
    loss_name: str,
) -> keras.Model:
    """Build a simple two-tower retrieval model with dot-product scoring."""
    user_input = keras.Input(shape=(user_dim,), name="user_features")
    item_input = keras.Input(shape=(item_dim,), name="item_features")

    def tower(x: tf.Tensor, prefix: str) -> tf.Tensor:
        x = layers.Dense(256, activation="relu", name=f"{prefix}_dense_1")(x)
        x = layers.Dropout(dropout, name=f"{prefix}_dropout_1")(x)
        x = layers.Dense(128, activation="relu", name=f"{prefix}_dense_2")(x)
        x = layers.Dense(embedding_dim, name=f"{prefix}_embedding")(x)
        return layers.Lambda(
            lambda t: tf.math.l2_normalize(t, axis=1), name=f"{prefix}_norm"
        )(x)

    user_vec = tower(user_input, "user")
    item_vec = tower(item_input, "item")

    dot = layers.Dot(axes=1, name="dot_product")([user_vec, item_vec])
    if loss_name == "softmax":
        neg = layers.Lambda(lambda t: -t, name="negative_logit")(dot)
        output = layers.Concatenate(name="class_logits")([neg, dot])
    else:
        output = layers.Activation("sigmoid", name="match_probability")(dot)

    return keras.Model(
        inputs={"user_features": user_input, "item_features": item_input},
        outputs=output,
        name="padly_two_tower_baseline",
    )


def generate_synthetic_data(
    samples: int,
    user_dim: int,
    item_dim: int,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic data so the baseline can run before real data exists."""
    rng = np.random.default_rng(seed)
    user_features = rng.normal(0, 1, size=(samples, user_dim)).astype(np.float32)
    item_features = rng.normal(0, 1, size=(samples, item_dim)).astype(np.float32)

    user_proj = rng.normal(0, 1, size=(user_dim, 16)).astype(np.float32)
    item_proj = rng.normal(0, 1, size=(item_dim, 16)).astype(np.float32)
    user_latent = user_features @ user_proj
    item_latent = item_features @ item_proj
    logits = (user_latent * item_latent).sum(axis=1) / np.sqrt(16.0)
    logits += rng.normal(0, 0.5, size=samples).astype(np.float32)

    labels = (1.0 / (1.0 + np.exp(-logits)) > 0.5).astype(np.float32)
    return user_features, item_features, labels


def load_npz_data(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load training arrays from npz with required keys."""
    data = np.load(path)
    required = {"user_features", "item_features", "labels"}
    missing = required - set(data.files)
    if missing:
        raise ValueError(
            f"Missing keys in npz: {', '.join(sorted(missing))}. "
            "Expected keys: user_features, item_features, labels"
        )

    user_features = data["user_features"].astype(np.float32)
    item_features = data["item_features"].astype(np.float32)
    labels = data["labels"].astype(np.float32).reshape(-1)

    if len(user_features) != len(item_features) or len(user_features) != len(labels):
        raise ValueError("user_features, item_features, and labels must have same length")
    if user_features.ndim != 2 or item_features.ndim != 2:
        raise ValueError("user_features and item_features must be 2D arrays")

    return user_features, item_features, labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Padly Two-Tower baseline model")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument(
        "--loss",
        choices=["binary_crossentropy", "softmax"],
        default="binary_crossentropy",
        help="Training loss function",
    )
    parser.add_argument("--embedding-dim", type=int, default=64)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--npz-path", type=Path, default=None)
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--user-dim", type=int, default=64)
    parser.add_argument("--item-dim", type=int, default=96)

    parser.add_argument(
        "--output-model",
        type=Path,
        default=Path("app/ai/artifacts/two_tower_baseline.keras"),
        help="Output path for trained Keras model",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tf.keras.utils.set_random_seed(args.seed)

    if args.npz_path:
        user_features, item_features, labels = load_npz_data(args.npz_path)
        user_dim = int(user_features.shape[1])
        item_dim = int(item_features.shape[1])
    else:
        user_dim = args.user_dim
        item_dim = args.item_dim
        user_features, item_features, labels = generate_synthetic_data(
            samples=args.samples,
            user_dim=user_dim,
            item_dim=item_dim,
            seed=args.seed,
        )

    split = int(0.8 * len(labels))
    train_x = {
        "user_features": user_features[:split],
        "item_features": item_features[:split],
    }
    val_x = {
        "user_features": user_features[split:],
        "item_features": item_features[split:],
    }
    train_y = labels[:split]
    val_y = labels[split:]

    model = build_model(
        user_dim=user_dim,
        item_dim=item_dim,
        embedding_dim=args.embedding_dim,
        dropout=args.dropout,
        loss_name=args.loss,
    )

    if args.loss == "softmax":
        train_y = train_y.astype(np.int32)
        val_y = val_y.astype(np.int32)
        loss_fn = keras.losses.SparseCategoricalCrossentropy(from_logits=True)
        metrics = [keras.metrics.SparseCategoricalAccuracy(name="accuracy")]
    else:
        loss_fn = keras.losses.BinaryCrossentropy()
        metrics = [
            keras.metrics.BinaryAccuracy(name="accuracy"),
            keras.metrics.AUC(name="auc"),
        ]

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=args.learning_rate),
        loss=loss_fn,
        metrics=metrics,
    )

    model.fit(
        train_x,
        train_y,
        validation_data=(val_x, val_y),
        epochs=args.epochs,
        batch_size=args.batch_size,
        verbose=2,
    )

    args.output_model.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.output_model)
    print(f"Saved model to: {args.output_model}")


if __name__ == "__main__":
    main()
