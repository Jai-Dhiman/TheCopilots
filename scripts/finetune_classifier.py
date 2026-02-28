"""Fine-tune Gemma 3 with LoRA on synthetic GD&T training data.

Runs on GCP GPU VM (NVIDIA RTX PRO 6000 Blackwell, 102GB VRAM).
Reads training pairs from data/synthetic/training_pairs.jsonl,
trains a LoRA adapter for the GD&T classification task, evaluates on
a held-out split, and saves the merged model for GGUF conversion.

VM deps: pip install transformers accelerate bitsandbytes peft datasets tqdm

Output:
- models/gemma3-gdt-lora/     -- LoRA adapter weights
- models/gemma3-gdt-merged/   -- merged full model (for GGUF conversion)
- models/eval_results.json    -- holdout evaluation metrics
- models/training_log.jsonl   -- per-epoch loss + metrics
"""

import argparse
import json
import random
import time
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, PeftModel
from tqdm import tqdm
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
)

BASE_DIR = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = BASE_DIR / "data" / "synthetic"
MODELS_DIR = BASE_DIR / "models"
DEFAULT_DATA_PATH = SYNTHETIC_DIR / "training_pairs.jsonl"

# --- Model Config ---

BASE_MODEL = "google/gemma-3-1b-it"
MAX_SEQ_LENGTH = 2048

# --- LoRA Config ---

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
TARGET_MODULES = ["q_proj", "v_proj"]

# --- Training Config ---

PER_DEVICE_TRAIN_BATCH_SIZE = 4
GRADIENT_ACCUMULATION_STEPS = 4  # effective batch 16
NUM_TRAIN_EPOCHS = 5
LEARNING_RATE = 2e-4
LR_SCHEDULER_TYPE = "cosine"
WARMUP_RATIO = 0.1
OPTIM = "adamw_8bit"

# --- Data Loading ---


def load_training_pairs(data_path: Path) -> list[dict]:
    """Load training pairs from JSONL file."""
    if not data_path.exists():
        raise FileNotFoundError(
            f"Training data not found: {data_path}\n"
            "Run generate_synthetic_data.py first."
        )
    pairs = []
    for line in data_path.read_text().strip().split("\n"):
        if line.strip():
            try:
                pairs.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in training data: {exc}") from exc
    if len(pairs) < 10:
        raise ValueError(f"Too few training pairs ({len(pairs)}). Need at least 10.")
    return pairs


def pair_to_instruction(pair: dict) -> str:
    """Convert a training pair to instruction-tuning format.

    The classifier learns to predict classification (not full_output).
    """
    input_json = json.dumps(pair["input"], ensure_ascii=False, indent=None)
    output_json = json.dumps(pair["classification"], ensure_ascii=False, indent=None)

    return (
        "<instruction>Given this part feature, classify the appropriate GD&T control.</instruction>\n"
        f"<input>{input_json}</input>\n"
        f"<output>{output_json}</output>"
    )


def prepare_datasets(pairs: list[dict], seed: int = 42) -> tuple[Dataset, Dataset, list[dict]]:
    """Split pairs 90/10 and convert to HuggingFace Dataset. Returns (train_ds, eval_ds, eval_pairs)."""
    rng = random.Random(seed)
    shuffled = list(pairs)
    rng.shuffle(shuffled)

    split_idx = int(len(shuffled) * 0.9)
    train_pairs = shuffled[:split_idx]
    eval_pairs = shuffled[split_idx:]

    train_texts = [pair_to_instruction(p) for p in train_pairs]
    eval_texts = [pair_to_instruction(p) for p in eval_pairs]

    train_ds = Dataset.from_dict({"text": train_texts})
    eval_ds = Dataset.from_dict({"text": eval_texts})

    print(f"Train: {len(train_ds)} examples, Eval: {len(eval_ds)} examples")
    return train_ds, eval_ds, eval_pairs


# --- Model Setup ---


def load_model_and_tokenizer(load_in_4bit: bool = False):
    """Load base model and tokenizer from HuggingFace."""
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if load_in_4bit:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.bfloat16,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            device_map="auto",
            torch_dtype=torch.bfloat16,
        )

    model.config.use_cache = False
    return model, tokenizer


def apply_lora(model):
    """Apply LoRA adapter to the model."""
    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


# --- Training ---


class TrainingLogger:
    """Log training metrics to JSONL file."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("")

    def log(self, entry: dict) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


LABEL_IGNORE_INDEX = -100
OUTPUT_TAG = "<output>"


def tokenize_dataset(ds: Dataset, tokenizer, max_length: int = MAX_SEQ_LENGTH) -> Dataset:
    """Tokenize a text dataset for causal LM training.

    Masks labels for everything BEFORE the <output> tag so the model
    only learns to predict the classification output, not the prompt.
    """
    # Pre-compute the token length of the output tag for offset calculation
    output_tag_tokens = tokenizer.encode(OUTPUT_TAG, add_special_tokens=False)
    output_tag_len = len(output_tag_tokens)

    def tokenize_fn(examples):
        all_input_ids = []
        all_labels = []
        all_attention_mask = []

        for text in examples["text"]:
            tokenized = tokenizer(
                text,
                truncation=True,
                max_length=max_length,
                padding="max_length",
            )
            input_ids = tokenized["input_ids"]
            attention_mask = tokenized["attention_mask"]

            # Find where <output> starts in the token sequence
            # The model should only be trained to predict tokens AFTER <output>
            labels = [LABEL_IGNORE_INDEX] * len(input_ids)

            # Find the output tag position by scanning for the token subsequence
            output_start = None
            for i in range(len(input_ids) - output_tag_len + 1):
                if input_ids[i:i + output_tag_len] == output_tag_tokens:
                    output_start = i + output_tag_len
                    break

            if output_start is not None:
                # Set labels only for the output portion (after <output> tag)
                for i in range(output_start, len(input_ids)):
                    if attention_mask[i] == 1:  # skip padding
                        labels[i] = input_ids[i]

            all_input_ids.append(input_ids)
            all_labels.append(labels)
            all_attention_mask.append(attention_mask)

        return {
            "input_ids": all_input_ids,
            "attention_mask": all_attention_mask,
            "labels": all_labels,
        }

    return ds.map(tokenize_fn, batched=True, remove_columns=["text"])


def train_model(model, tokenizer, train_ds: Dataset, eval_ds: Dataset,
                num_epochs: int, logger: TrainingLogger):
    """Run LoRA fine-tuning with HuggingFace Trainer."""
    output_dir = MODELS_DIR / "gemma3-gdt-lora"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Tokenize datasets
    print("Tokenizing datasets...")
    train_tokenized = tokenize_dataset(train_ds, tokenizer)
    eval_tokenized = tokenize_dataset(eval_ds, tokenizer)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=PER_DEVICE_TRAIN_BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        num_train_epochs=num_epochs,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type=LR_SCHEDULER_TYPE,
        warmup_ratio=WARMUP_RATIO,
        optim=OPTIM,
        bf16=True,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        seed=42,
        report_to="none",
        gradient_checkpointing=True,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=eval_tokenized,
    )

    print(f"\nStarting training: {num_epochs} epochs, lr={LEARNING_RATE}")
    start_time = time.time()
    result = trainer.train()
    elapsed = time.time() - start_time

    print(f"Training completed in {elapsed:.0f}s")
    print(f"  Final train loss: {result.training_loss:.4f}")

    logger.log({
        "event": "training_complete",
        "epochs": num_epochs,
        "train_loss": result.training_loss,
        "elapsed_seconds": elapsed,
        "timestamp": time.time(),
    })

    # Save LoRA adapter weights
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    print(f"LoRA weights saved to: {output_dir}")

    return trainer


# --- Model Merge + Export ---


def merge_and_save(model, tokenizer) -> None:
    """Merge LoRA weights into base model and save for GGUF conversion."""
    merged_dir = MODELS_DIR / "gemma3-gdt-merged"
    merged_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nMerging LoRA into base model...")
    merged_model = model.merge_and_unload()
    merged_model.save_pretrained(str(merged_dir))
    tokenizer.save_pretrained(str(merged_dir))
    print(f"Merged model saved to: {merged_dir}")
    print(f"\nTo convert to GGUF (on the VM):")
    print(f"  pip install gguf")
    print(f"  git clone --depth 1 https://github.com/ggml-org/llama.cpp")
    print(f"  python3 llama.cpp/convert_hf_to_gguf.py {merged_dir} --outfile {MODELS_DIR}/gemma3-gdt-f16.gguf --outtype f16")
    print(f"  cd llama.cpp && cmake -B build && cmake --build build --config Release -j$(nproc)")
    print(f"  ./llama.cpp/build/bin/llama-quantize {MODELS_DIR}/gemma3-gdt-f16.gguf {MODELS_DIR}/gemma3-gdt-q4km.gguf Q4_K_M")


# --- Evaluation ---


def run_evaluation(model, tokenizer, eval_pairs: list[dict]) -> dict:
    """Run the fine-tuned model on held-out pairs and compute metrics."""
    model.config.use_cache = True
    model.eval()

    metrics = {
        "total": len(eval_pairs),
        "symbol_correct": 0,
        "primary_control_correct": 0,
        "datum_required_correct": 0,
        "modifier_correct": 0,
        "parse_failures": 0,
        "predictions": [],
    }

    print(f"\nEvaluating on {len(eval_pairs)} pairs...")
    for pair in tqdm(eval_pairs, desc="Evaluating"):
        input_json = json.dumps(pair["input"], ensure_ascii=False, indent=None)
        prompt = (
            "<instruction>Given this part feature, classify the appropriate GD&T control.</instruction>\n"
            f"<input>{input_json}</input>\n"
            "<output>"
        )

        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.1,
                do_sample=True,
            )
        decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract the output portion
        try:
            output_start = decoded.index("<output>") + len("<output>")
            output_end = decoded.index("</output>") if "</output>" in decoded else len(decoded)
            pred_text = decoded[output_start:output_end].strip()
            pred = json.loads(pred_text)
        except (ValueError, json.JSONDecodeError):
            metrics["parse_failures"] += 1
            metrics["predictions"].append({
                "input": pair["input"],
                "expected": pair["classification"],
                "predicted_raw": decoded[-200:],
                "status": "parse_error",
            })
            continue

        expected = pair["classification"]

        if pred.get("symbol") == expected.get("symbol"):
            metrics["symbol_correct"] += 1
        if pred.get("primary_control") == expected.get("primary_control"):
            metrics["primary_control_correct"] += 1
        if pred.get("datum_required") == expected.get("datum_required"):
            metrics["datum_required_correct"] += 1
        if pred.get("modifier") == expected.get("modifier"):
            metrics["modifier_correct"] += 1

        metrics["predictions"].append({
            "input": pair["input"],
            "expected": expected,
            "predicted": pred,
            "status": "ok",
        })

    # Compute accuracy rates
    valid = metrics["total"] - metrics["parse_failures"]
    if valid > 0:
        metrics["symbol_accuracy"] = metrics["symbol_correct"] / valid
        metrics["primary_control_accuracy"] = metrics["primary_control_correct"] / valid
        metrics["datum_required_accuracy"] = metrics["datum_required_correct"] / valid
        metrics["modifier_accuracy"] = metrics["modifier_correct"] / valid
    else:
        metrics["symbol_accuracy"] = 0.0
        metrics["primary_control_accuracy"] = 0.0
        metrics["datum_required_accuracy"] = 0.0
        metrics["modifier_accuracy"] = 0.0

    metrics["parse_failure_rate"] = metrics["parse_failures"] / metrics["total"]

    return metrics


def print_eval_results(metrics: dict) -> None:
    """Print evaluation results."""
    print(f"\n=== Evaluation Results ===")
    print(f"Total: {metrics['total']} pairs")
    print(f"Parse failures: {metrics['parse_failures']} ({metrics['parse_failure_rate']:.1%})")
    print(f"Symbol accuracy:          {metrics['symbol_accuracy']:.1%}")
    print(f"Primary control accuracy: {metrics['primary_control_accuracy']:.1%}")
    print(f"Datum required accuracy:  {metrics['datum_required_accuracy']:.1%}")
    print(f"Modifier accuracy:        {metrics['modifier_accuracy']:.1%}")


# --- Main ---


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune Gemma 3 for GD&T classification")
    parser.add_argument("--eval-only", action="store_true", help="Load saved weights and run evaluation only")
    parser.add_argument("--epochs", type=int, default=NUM_TRAIN_EPOCHS, help="Number of training epochs")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA_PATH), help="Path to training JSONL")
    parser.add_argument("--load-in-4bit", action="store_true", help="Load base model in 4-bit (saves VRAM)")
    args = parser.parse_args()

    data_path = Path(args.data)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Check GPU
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available. This script requires a GPU.")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.0f} GB")

    # Load data
    print(f"\nLoading training data from: {data_path}")
    all_pairs = load_training_pairs(data_path)
    print(f"Loaded {len(all_pairs)} training pairs")

    # Prepare datasets (90/10 split, seed=42)
    train_ds, eval_ds, eval_pairs = prepare_datasets(all_pairs, seed=42)

    # Load model
    print(f"\nLoading model: {BASE_MODEL} (4bit={args.load_in_4bit})")
    model, tokenizer = load_model_and_tokenizer(load_in_4bit=args.load_in_4bit)

    lora_dir = MODELS_DIR / "gemma3-gdt-lora"
    logger = TrainingLogger(MODELS_DIR / "training_log.jsonl")

    if args.eval_only:
        if not lora_dir.exists():
            raise FileNotFoundError(
                f"LoRA weights not found: {lora_dir}\n"
                "Run training first (without --eval-only)."
            )
        print(f"Loading LoRA weights from: {lora_dir}")
        model = PeftModel.from_pretrained(model, str(lora_dir))
    else:
        # Apply LoRA and train
        model = apply_lora(model)
        print(f"LoRA config: r={LORA_R}, alpha={LORA_ALPHA}, targets={TARGET_MODULES}")

        train_model(model, tokenizer, train_ds, eval_ds, args.epochs, logger)

    # Run evaluation
    metrics = run_evaluation(model, tokenizer, eval_pairs)
    print_eval_results(metrics)

    # Save eval results (exclude per-prediction details for the summary)
    eval_summary = {k: v for k, v in metrics.items() if k != "predictions"}
    eval_path = MODELS_DIR / "eval_results.json"
    eval_path.write_text(json.dumps(eval_summary, indent=2))
    print(f"\nEval results saved to: {eval_path}")

    logger.log({
        "event": "evaluation_complete",
        **eval_summary,
        "timestamp": time.time(),
    })

    # Merge and save (skip on eval-only)
    if not args.eval_only:
        merge_and_save(model, tokenizer)

    print(f"\nDone. Next steps:")
    print(f"  1. Convert merged model to GGUF (see instructions above)")
    print(f"  2. Copy .gguf file to local machine")
    print(f"  3. Create Ollama Modelfile and import:")
    print(f'     ollama create gemma3-270m-gdt -f Modelfile')
    print(f"  4. Run: python scripts/validate_pipeline.py --verbose")


if __name__ == "__main__":
    main()
