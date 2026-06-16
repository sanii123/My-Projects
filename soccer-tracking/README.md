# Soccer Player Tracking Pipeline

A deep learning pipeline for automated player detection, tracking, and team classification in soccer match footage. Built as a mini-project for the Deep Learning for Cognitive Computing course at the University of Jyväskylä.

## Overview

The pipeline processes raw match video and outputs an annotated version with per-player bounding boxes, persistent track IDs, and team labels — without any manual annotation or predefined team colors.

## Pipeline

```
Input Video
    │
    ▼
YOLOv8 (Player Detection)
    │
    ▼
ByteTrack (Multi-Object Tracking)
    │
    ▼
SigLIP (Visual Embeddings per player crop)
    │
    ▼
KMeans Clustering (Team Assignment)
    │
    ▼
Annotated Output Video
```

## Tech Stack

| Component | Purpose |
|-----------|---------|
| YOLOv8 | Real-time player and ball detection |
| ByteTrack | Multi-object tracking with persistent IDs across frames |
| SigLIP | Vision-language model used to extract player crop embeddings |
| KMeans | Unsupervised clustering to separate players into two teams |
| OpenCV | Video I/O and frame-level annotation |

## Key Design Choices

- **SigLIP over color histograms** — jersey color alone fails under varying lighting and similar team kits. SigLIP embeddings capture richer visual features for more robust team separation.
- **ByteTrack for low-confidence detections** — unlike SORT, ByteTrack retains partially occluded players instead of dropping their track, reducing ID switches during crowded play.
- **Unsupervised team assignment** — KMeans runs on the embedding space so no labeled data or prior knowledge of team colors is needed.

## How to Run

```bash
pip install -r requirements.txt
python main.py --input your_match_video.mp4 --output output.mp4
```

## Output

Annotated video with:
- Bounding boxes per detected player
- Persistent track IDs across frames
- Team label (Team A / Team B) per player
- Ball tracking

## Results

The pipeline successfully tracks players across frames with consistent team assignments, handling partial occlusions and re-entries. ID switches remain low in open-play situations; performance degrades slightly in dense cluster scenarios (corners, set pieces).

## Course

Deep Learning for Cognitive Computing — University of Jyväskylä, 2024
