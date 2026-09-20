# Model card — forward-looking-claim detector

A sentence classifier that decides whether a transcript sentence is a forward-looking
commitment by management (guidance, a target, an expectation about a future period).
It is the candidate for replacing the cue regex that gates which sentences Walk the
Talk sends to the LLM for claim extraction. **It is not in the pipeline yet** — see
"Should it be used".

## Data

- Sentences: every prose sentence of the four Infosys earnings-call transcripts in the
  PDF corpus (Q4 FY25, Q1 FY26, Q4 FY26, Q1 FY27), 1,729 after de-duplication.
- Gold (held out, never trained on): 69 hand-labelled sentences — 28 positives (the 25
  Walk-the-Talk claims plus `eval/gold/claim_positives.txt`) and 41 negatives
  (`eval/gold/claim_negatives.txt`, checked by hand: past-tense results, analyst
  questions, hopes without a commitment).
- Silver (training): 1,641 sentences labelled by the LLM as teacher
  (`python -m finsight.ml.claims.dataset --label-with-llm`, `gpt-oss-120b`):
  - 1,369 sentences with no forward-looking cue → negative (the cue regex has 0.96
    recall on gold, so this is ~4% label noise on the positive side);
  - 359 cue-passing sentences classified yes/no by the LLM in batches of 20 →
    63 positives, 209 negatives (a batch that returned no JSON kept the labels the
    extraction runs had given: 14 positives, 83 negatives).
- Split: 85/15 of silver for training/validation, seed 13.

## Training

`answerdotai/ModernBERT-base`, sequence classification head, plain PyTorch, Apple
silicon (MPS). Class-weighted cross-entropy (positive weight = negatives/positives),
batch 16, AdamW, linear warm-up and decay. Two runs:

| run | epochs | lr | val F1 | gold precision | gold recall | gold F1 |
|---|---|---|---|---|---|---|
| 1 (41 silver positives from the extraction runs) | 3 | 3e-5 | 0.400 | 0.667 | 0.429 | 0.522 |
| 2 (63 positives after direct LLM labelling) | 8 | 5e-5 | 0.667 | **0.941** | 0.571 | **0.711** |

Baselines on the same 68 gold sentences:

| baseline | precision | recall | F1 |
|---|---|---|---|
| cue regex (`is_candidate`, what the pipeline uses today) | 0.403 | **0.964** | 0.568 |
| `yiyanghkust/finbert-fls` zero-shot (Specific/Non-specific FLS → positive) | 0.649 | 0.857 | **0.739** |
| fine-tuned ModernBERT, run 2 | **0.941** | 0.571 | 0.711 |

Full numbers: `eval/results/claim_detector.json`. Weights are written to
`models/claim-detector/` (not committed; `make train-claim-detector` reproduces them
in about six minutes).

## Should it be used

Not as the gate. The gate's job is recall — a claim the gate drops can never be graded —
and the regex's 0.96 recall is the number that matters there; the classifier's 0.57
would silently lose four in ten commitments. Training loss reaches zero by epoch 5 on
63 positives: the model has memorised the teacher's positives rather than learned the
category, and validation recall is flat at 0.5 from epoch 3.

What it is good for: precision. At 0.94 precision it could *rank* candidates when a
long transcript produces more cue sentences than the extraction budget allows, or flag
"the LLM extracted this but the classifier disagrees" for review. Neither is wired in.

What would change the picture: positives. Every gain between run 1 and run 2 came from
22 more positive examples. A second company's transcripts labelled the same way would
roughly double them; five companies would make this a real training set. The dataset
and training scripts already handle that — it is a data problem, not a code problem.

## Caveats

- Silver labels come from one LLM on one company; the classifier inherits its blind
  spots (conversational commitments without a cue word, e.g. "closing formalities will
  take a few weeks", are under-represented).
- Gold has 28 positives; ±1 sentence moves recall by 3.6 points.
- No hyper-parameter search beyond the two runs above; no ensembling with FinBERT-FLS,
  which at 0.86 recall / 0.65 precision may be the better single model for this corpus.
