# Ground-photo classifier v2 — evaluation

Model: MobileNetV3-Small-Plantation 2.0.0 (MobileNetV3-Small), initialised from plantation_classifier_v1.pt (previous project checkpoint).
Trained 2026-10-08T07:48:28+00:00 on CPU. Split sizes: {'train': 6127, 'val': 683, 'test': 1420}.

## Data
Real photographs from the Intel Image Classification dataset (GitHub mirror luangtatipsy/intel-image-classification @ fbb0210). plantation = 'forest' photos; non_plantation = 'buildings', 'street', 'sea', 'glacier'; unclear_evidence = real photos with synthetic blur/darkness/over-exposure/occlusion. See ml/build_real_dataset.py.

## Held-out test set (real photos, never seen in training)

Accuracy **0.984**, macro F1 **0.984**.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| non_plantation | 0.977 | 0.981 | 0.979 | 472 |
| plantation | 0.981 | 0.992 | 0.986 | 474 |
| unclear_evidence | 0.994 | 0.979 | 0.986 | 474 |

Confusion matrix (rows = true, columns = predicted):

| | non_plantation | plantation | unclear_evidence |
|---|---|---|---|
| **non_plantation** | 463 | 7 | 2 |
| **plantation** | 3 | 470 | 1 |
| **unclear_evidence** | 8 | 2 | 464 |

## Training history

| Epoch | Train loss | Train acc | Val acc |
|---|---|---|---|
| 1 | 0.327 | 0.951 | 0.999 |
| 2 | 0.2191 | 0.984 | 0.991 |
| 3 | 0.205 | 0.987 | 0.993 |
| 4 | 0.1978 | 0.991 | 0.996 |
| 5 | 0.1916 | 0.994 | 0.996 |
| 6 | 0.1894 | 0.994 | 0.996 |

## Limits — read before quoting these numbers
- Test metrics are on the source dataset's held-out test split (real photos, never used in training). The dataset contains no areca/coconut/agroforestry plantation photos, so accuracy on real plantation field photos has NOT been measured.
- "unclear_evidence" examples are real photos degraded synthetically; real bad field photos may look different.
- Some source labels are noisy (for example, a few "glacier" photos show green slopes).

## Comparison and extra checks (run 2026-10-08)

| Check | Result |
|---|---|
| Old model (v1, trained on synthetic images) on the same real test set | accuracy **0.496**: it labelled 317 of 474 forest photos as non-plantation and only 5 correctly |
| New model (v2) on the same real test set | accuracy **0.984** |
| v2 on 200 clean "mountain" test photos (a class it was never trained on; not in the accuracy above) | 192 non_plantation, 6 plantation, 2 unclear |
| Training time | ~12 minutes on 2 CPU cores (6 epochs) |

Reproduce: `python ml/build_real_dataset.py && python ml/train.py && python ml/evaluate.py`.
