
################## detection image creation 
# import cv2
# from PIL import Image
# import supervision as sv
# from inference import get_model

# PLAYER_DETECTION_MODEL_ID = "football-players-detection-3zvbc/9"
# player_model = get_model(model_id=PLAYER_DETECTION_MODEL_ID)

# frame_path = "test_frame.png"
# frame_bgr = cv2.imread(frame_path)
# if frame_bgr is None:
#     raise FileNotFoundError(f"Could not read image: {frame_path}")

# frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
# pil_image = Image.fromarray(frame_rgb)

# result = player_model.infer(pil_image, confidence=0.3)[0]
# detections = sv.Detections.from_inference(result)

# print(detections.xyxy.shape)
# print(detections.class_id)

# # Annotate and save
# CLASS_NAMES = {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}

# box_annotator = sv.BoxAnnotator()
# label_annotator = sv.LabelAnnotator()

# labels = [
#     f"{CLASS_NAMES.get(cid, 'unknown')} {conf:.2f}"
#     for cid, conf in zip(detections.class_id, detections.confidence)
# ]

# annotated = box_annotator.annotate(frame_bgr.copy(), detections)
# annotated = label_annotator.annotate(annotated, detections, labels=labels)

# cv2.imwrite("detections.jpg", annotated)
# print("Saved detections.jpg")




# #####################################################

# import cv2
# from PIL import Image
# import supervision as sv
# from inference import get_model

# PLAYER_DETECTION_MODEL_ID = "football-players-detection-3zvbc/9"
# CLASS_NAMES = {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}

# player_model = get_model(model_id=PLAYER_DETECTION_MODEL_ID)
# tracker = sv.ByteTrack()

# box_annotator = sv.BoxAnnotator()
# label_annotator = sv.LabelAnnotator()

# cap = cv2.VideoCapture("match.mp4")
# fps = cap.get(cv2.CAP_PROP_FPS)
# width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
# height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# writer = cv2.VideoWriter(
#     "Output_tracked.mp4",
#     cv2.VideoWriter_fourcc(*"mp4v"),
#     fps,
#     (width, height),
# )

# frame_idx = 0
# while True:
#     ok, frame_bgr = cap.read()
#     if not ok:
#         break

#     frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
#     pil_image = Image.fromarray(frame_rgb)

#     result = player_model.infer(pil_image, confidence=0.3)[0]
#     detections = sv.Detections.from_inference(result)
#     detections = tracker.update_with_detections(detections)

#     labels = [
#         f"#{tid} {CLASS_NAMES.get(cid, '?')}"
#         for tid, cid in zip(detections.tracker_id, detections.class_id)
#     ]

#     annotated = box_annotator.annotate(frame_bgr.copy(), detections)
#     annotated = label_annotator.annotate(annotated, detections, labels=labels)
#     writer.write(annotated)

#     frame_idx += 1
#     if frame_idx % 30 == 0:
#         print(f"Processed {frame_idx} frames")

# cap.release()
# writer.release()
# print(f"Done. Saved output_tracked.mp4 ({frame_idx} frames)")



################################################################


# import cv2
# import torch
# import numpy as np
# from PIL import Image
# import supervision as sv
# from collections import defaultdict
# from sklearn.cluster import KMeans
# from transformers import AutoProcessor, SiglipVisionModel
# from inference import get_model

# PLAYER_DETECTION_MODEL_ID = "football-players-detection-3zvbc/9"
# SIGLIP_MODEL = "google/siglip-base-patch16-224"
# BOOTSTRAP_FRAMES = 50
# MIN_CROPS_PER_PLAYER = 3
# CLASS_NAMES = {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}

# device = "cuda" if torch.cuda.is_available() else "cpu"
# print(f"Using device: {device}")

# player_model = get_model(model_id=PLAYER_DETECTION_MODEL_ID)
# processor = AutoProcessor.from_pretrained(SIGLIP_MODEL)
# embedder = SiglipVisionModel.from_pretrained(SIGLIP_MODEL).to(device).eval()
# tracker = sv.ByteTrack()


# @torch.no_grad()
# def embed_crops(crops):
#     """Return one embedding vector per crop."""
#     if not crops:
#         return np.zeros((0, 768))
#     batch = processor(images=crops, return_tensors="pt").to(device)
#     out = embedder(**batch)
#     return out.pooler_output.cpu().numpy()


# def crop_player(frame_bgr, xyxy):
#     """Cut out the player crop, upper half only (jersey area)."""
#     x1, y1, x2, y2 = map(int, xyxy)
#     h = y2 - y1
#     crop = frame_bgr[y1:y1 + h // 2, x1:x2]
#     if crop.size == 0:
#         return None
#     rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
#     return Image.fromarray(rgb)


# # Pass 1: bootstrap - collect crops per tracker_id from first N frames
# bootstrap_crops = defaultdict(list)

# cap = cv2.VideoCapture("clip.mp4")
# for _ in range(BOOTSTRAP_FRAMES):
#     ok, frame_bgr = cap.read()
#     if not ok:
#         break

#     pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
#     result = player_model.infer(pil, confidence=0.3)[0]
#     detections = sv.Detections.from_inference(result)
#     detections = tracker.update_with_detections(detections)

#     players_mask = detections.class_id == 2
#     for tid, xyxy in zip(
#         detections.tracker_id[players_mask],
#         detections.xyxy[players_mask],
#     ):
#         if len(bootstrap_crops[tid]) < MIN_CROPS_PER_PLAYER:
#             crop = crop_player(frame_bgr, xyxy)
#             if crop is not None:
#                 bootstrap_crops[tid].append(crop)

# cap.release()
# print(f"Collected crops for {len(bootstrap_crops)} unique players")

# # One embedding per tracker_id (averaged across their crops)
# player_ids = []
# player_embeddings = []
# for tid, crops in bootstrap_crops.items():
#     if len(crops) >= MIN_CROPS_PER_PLAYER:
#         emb = embed_crops(crops).mean(axis=0)
#         player_ids.append(tid)
#         player_embeddings.append(emb)

# player_embeddings = np.array(player_embeddings)
# print(f"Embedded {len(player_ids)} players")

# # Cluster into 2 teams
# kmeans = KMeans(n_clusters=2, n_init=10, random_state=42)
# team_assignments = kmeans.fit_predict(player_embeddings)
# team_lookup = dict(zip(player_ids, team_assignments))
# print(f"Team A: {sum(team_assignments == 0)} players, "
#       f"Team B: {sum(team_assignments == 1)} players")

# # Pass 2: render the full video with team colors
# tracker = sv.ByteTrack()  # reset so IDs match what we clustered
# TEAM_COLORS = {0: sv.Color(220, 60, 60), 1: sv.Color(60, 90, 220)}

# cap = cv2.VideoCapture("clip.mp4")
# fps = cap.get(cv2.CAP_PROP_FPS)
# W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
# H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
# writer = cv2.VideoWriter(
#     "output_teams.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H)
# )

# frame_idx = 0
# while True:
#     ok, frame_bgr = cap.read()
#     if not ok:
#         break

#     pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
#     result = player_model.infer(pil, confidence=0.3)[0]
#     detections = sv.Detections.from_inference(result)
#     detections = tracker.update_with_detections(detections)

#     # Classify any new tracker_ids that appeared after bootstrap
#     players_mask = detections.class_id == 2
#     new_crops_by_id = defaultdict(list)
#     for tid, xyxy in zip(
#         detections.tracker_id[players_mask],
#         detections.xyxy[players_mask],
#     ):
#         if tid not in team_lookup:
#             crop = crop_player(frame_bgr, xyxy)
#             if crop is not None:
#                 new_crops_by_id[tid].append(crop)

#     if new_crops_by_id:
#         new_ids = list(new_crops_by_id.keys())
#         new_embs = np.array([
#             embed_crops(new_crops_by_id[tid]).mean(axis=0)
#             for tid in new_ids
#         ])
#         for tid, t in zip(new_ids, kmeans.predict(new_embs)):
#             team_lookup[tid] = int(t)

#     # Draw colored boxes per detection
#     annotated = frame_bgr.copy()
#     for tid, cid, xyxy in zip(
#         detections.tracker_id,
#         detections.class_id,
#         detections.xyxy,
#     ):
#         x1, y1, x2, y2 = map(int, xyxy)
#         if cid == 2:
#             team = team_lookup.get(tid)
#             color = TEAM_COLORS.get(team, sv.Color(200, 200, 200)).as_bgr()
#         elif cid == 3:
#             color = (0, 200, 200)  # referee yellow
#         elif cid == 1:
#             color = (200, 0, 200)  # goalkeeper magenta
#         else:
#             color = (0, 255, 255)  # ball
#         cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
#         cv2.putText(
#             annotated, f"#{tid}", (x1, y1 - 6),
#             cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
#         )

#     writer.write(annotated)
#     frame_idx += 1
#     if frame_idx % 30 == 0:
#         print(f"Processed {frame_idx} frames")

# cap.release()
# writer.release()
# print(f"Done. Saved output_teams.mp4")

########################################################################################


"""
Soccer Tracking and Tactical Analysis
Pipeline: Video -> Detection (YOLO) -> Tracking (ByteTrack) -> Team ID (SigLIP + KMeans) -> Annotated Video
"""

import cv2
import torch
import numpy as np
from PIL import Image
import supervision as sv
from collections import defaultdict
from sklearn.cluster import KMeans
from transformers import AutoProcessor, SiglipVisionModel
from inference import get_model


# Configuration
# What: model IDs, bootstrap settings, and class mapping.
# How: BOOTSTRAP_FRAMES sets how many frames pass 1 uses; MIN_CROPS_PER_PLAYER
# is the minimum observations before a player is considered for clustering.
PLAYER_DETECTION_MODEL_ID = "football-players-detection-3zvbc/9"
SIGLIP_MODEL = "google/siglip-base-patch16-224"
BOOTSTRAP_FRAMES = 50
MIN_CROPS_PER_PLAYER = 3
CLASS_NAMES = {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")


# Model loading
# What: instantiate the YOLO detector, SigLIP embedder, and ByteTrack tracker.
# How: loaded once at startup and reused for every frame. SigLIP is frozen
# (.eval()) so no weights update during inference.
player_model = get_model(model_id=PLAYER_DETECTION_MODEL_ID)
processor = AutoProcessor.from_pretrained(SIGLIP_MODEL)
embedder = SiglipVisionModel.from_pretrained(SIGLIP_MODEL).to(device).eval()
tracker = sv.ByteTrack()


# Embedding function
# What: turns a list of player crops into 768-dim semantic vectors.
# How: SigLIP processes a batch of images and returns one pooled embedding per
# image. @torch.no_grad() skips gradient tracking since we don't train SigLIP.
@torch.no_grad()
def embed_crops(crops):
    if not crops:
        return np.zeros((0, 768))
    batch = processor(images=crops, return_tensors="pt").to(device)
    out = embedder(**batch)
    return out.pooler_output.cpu().numpy()


# Crop extraction
# What: cut out the upper half of a player's bounding box (jersey area).
# How: skip the lower half (shorts/grass) to maximize team signal. Convert
# BGR (OpenCV) to RGB (PIL) before returning, since SigLIP expects PIL/RGB.
def crop_player(frame_bgr, xyxy):
    x1, y1, x2, y2 = map(int, xyxy)
    h = y2 - y1
    crop = frame_bgr[y1:y1 + h // 2, x1:x2]
    if crop.size == 0:
        return None
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


# Pass 1: bootstrap
# What: collect crops for each tracker_id over the first N frames.
# How: run detection + tracking on each frame, then store up to MIN_CROPS_PER_PLAYER
# crops per unique player. Goalkeepers and referees are excluded (class_id == 2 filter).
bootstrap_crops = defaultdict(list)

cap = cv2.VideoCapture("clip.mp4")
for _ in range(BOOTSTRAP_FRAMES):
    ok, frame_bgr = cap.read()
    if not ok:
        break

    pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    result = player_model.infer(pil, confidence=0.3)[0]
    detections = sv.Detections.from_inference(result)
    detections = tracker.update_with_detections(detections)

    players_mask = detections.class_id == 2
    for tid, xyxy in zip(
        detections.tracker_id[players_mask],
        detections.xyxy[players_mask],
    ):
        if len(bootstrap_crops[tid]) < MIN_CROPS_PER_PLAYER:
            crop = crop_player(frame_bgr, xyxy)
            if crop is not None:
                bootstrap_crops[tid].append(crop)

cap.release()
print(f"Collected crops for {len(bootstrap_crops)} unique players")


# Per-player embedding
# What: one averaged embedding per tracker_id.
# How: embed all of a player's crops, then take the mean. Averaging cancels out
# per-frame noise (motion blur, occlusion) leaving the team signal dominant.
player_ids = []
player_embeddings = []
for tid, crops in bootstrap_crops.items():
    if len(crops) >= MIN_CROPS_PER_PLAYER:
        emb = embed_crops(crops).mean(axis=0)
        player_ids.append(tid)
        player_embeddings.append(emb)

player_embeddings = np.array(player_embeddings)
print(f"Embedded {len(player_ids)} players")


# Unsupervised team clustering
# What: split players into 2 groups using KMeans on their embeddings.
# How: no labels needed; KMeans finds the team boundary as the dominant axis of
# variation. n_init=10 retries with different seeds and picks the best result.
kmeans = KMeans(n_clusters=2, n_init=10, random_state=42)
team_assignments = kmeans.fit_predict(player_embeddings)
team_lookup = dict(zip(player_ids, team_assignments))
print(f"Team A: {sum(team_assignments == 0)} players, "
      f"Team B: {sum(team_assignments == 1)} players")


# Pass 2: render annotated video
# What: reset the tracker, then re-process the full video with team-colored boxes.
# How: tracker reset is required so tracker_ids match those used in pass 1.
# Output is written to output_teams.mp4 at the same fps/resolution as the input.
tracker = sv.ByteTrack()
TEAM_COLORS = {0: sv.Color(220, 60, 60), 1: sv.Color(60, 90, 220)}

cap = cv2.VideoCapture("clip.mp4")
fps = cap.get(cv2.CAP_PROP_FPS)
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
writer = cv2.VideoWriter(
    "output_teams.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H)
)

frame_idx = 0
while True:
    ok, frame_bgr = cap.read()
    if not ok:
        break

    pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    result = player_model.infer(pil, confidence=0.3)[0]
    detections = sv.Detections.from_inference(result)
    detections = tracker.update_with_detections(detections)

    # Late-joiner handling
    # What: classify players who first appear after the bootstrap phase.
    # How: collect their crops, embed and average, then assign via the already-fit
    # KMeans (predict, not fit_predict). Cache the result in team_lookup.
    players_mask = detections.class_id == 2
    new_crops_by_id = defaultdict(list)
    for tid, xyxy in zip(
        detections.tracker_id[players_mask],
        detections.xyxy[players_mask],
    ):
        if tid not in team_lookup:
            crop = crop_player(frame_bgr, xyxy)
            if crop is not None:
                new_crops_by_id[tid].append(crop)

    if new_crops_by_id:
        new_ids = list(new_crops_by_id.keys())
        new_embs = np.array([
            embed_crops(new_crops_by_id[tid]).mean(axis=0)
            for tid in new_ids
        ])
        for tid, t in zip(new_ids, kmeans.predict(new_embs)):
            team_lookup[tid] = int(t)

    # Class-aware rendering
    # What: draw colored boxes and tracker IDs on the frame.
    # How: players get team color from team_lookup; goalkeepers, referees, and ball
    # get fixed colors so they don't get forced into the two team clusters.
    annotated = frame_bgr.copy()
    for tid, cid, xyxy in zip(
        detections.tracker_id,
        detections.class_id,
        detections.xyxy,
    ):
        x1, y1, x2, y2 = map(int, xyxy)
        if cid == 2:
            team = team_lookup.get(tid)
            color = TEAM_COLORS.get(team, sv.Color(200, 200, 200)).as_bgr()
        elif cid == 3:
            color = (0, 200, 200)  # referee yellow
        elif cid == 1:
            color = (200, 0, 200)  # goalkeeper magenta
        else:
            color = (0, 255, 255)  # ball
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated, f"#{tid}", (x1, y1 - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
        )

    writer.write(annotated)
    frame_idx += 1
    if frame_idx % 30 == 0:
        print(f"Processed {frame_idx} frames")

cap.release()
writer.release()
print(f"Done. Saved output_teams.mp4")
