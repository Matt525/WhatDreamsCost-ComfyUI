# API Director Spike

## Objective

Preserve the LTX Director timeline experience while replacing the local LTX model path with provider-backed generation, starting with fal.ai Seedance.

The critical product behavior is timeline-first generation:

1. A clip exists on the timeline before generation finishes.
2. The clip can be dragged, trimmed, copied, replaced, and retaken in place.
3. Video and audio remain separate timeline lanes.
4. Returned provider assets fill the existing clip slot instead of becoming detached outputs.

## Current Architecture

The UI is mostly contained in `js/ltx_director.js`.

- `TimelineEditor` owns state, selection, zoom, playback, drag/drop, canvas rendering, and synchronization into hidden ComfyUI widgets.
- Timeline state is serialized into the hidden `timeline_data` widget as:
  - `segments`: image/text video-lane clips
  - `audioSegments`: audio-lane clips
- Upload handlers already create placed clips:
  - `handleImageUpload(...)` uploads image assets and inserts image segments.
  - `handleAudioUpload(...)` uploads audio assets, calculates waveform peaks, and inserts audio segments.
- `render()` draws the video lane, audio lane, waveform visuals, ruler, playhead, handles, and out-of-duration overlay.
- `commitChanges()` serializes timeline state and also derives the LTX-specific `local_prompts`, `segment_lengths`, and `guide_strength` widgets.

The backend is currently LTX-specific in `ltx_director.py`.

- `define_schema()` requires model, clip, VAE, and latent-style inputs.
- `execute()` converts timeline image segments into LTX guide data.
- It creates or accepts LTX video latents.
- It runs PromptRelay attention patching.
- It optionally converts timeline audio into audio latents.
- It outputs LTX model/conditioning/latents/guide data plus combined audio.

## What To Preserve

- The timeline UI and canvas rendering.
- Separate video/image/text and audio lanes.
- Drag/drop placement and ghost-preview behavior.
- Audio waveform calculation and playback.
- Context menus for copy, paste, delete, replace.
- Frame/seconds display modes.
- Timeline JSON save/load.
- Clip prompt editing.
- Clip bounds, trim, and gap placement logic.

## What To Replace

- LTX-only schema inputs: `model`, `clip`, `audio_vae`, `optional_latent`.
- LTX outputs: `model`, `positive`, `video_latent`, `audio_latent`, `guide_data`.
- PromptRelay attention patching.
- VAE and latent generation.
- LTX guide-strength semantics where the provider does not support them.

## Proposed API-Backed Shape

Create a new node instead of mutating `LTXDirector` directly:

- Python: `api_director.py`
- Frontend: `js/api_director.js`
- Display name: `API Director`

Initial inputs:

- `provider`: `fal_seedance`
- `model`: provider-specific option, default Seedance 2.0
- `global_prompt`
- `timeline_data`
- `duration_frames`
- `duration_seconds`
- `frame_rate`
- `aspect_ratio`
- `resolution`
- `generate_audio`
- `seed`

Initial outputs:

- `video_path` or file reference
- `audio` or combined timeline audio
- `timeline_data`
- optionally a JSON manifest of generated clips/jobs

Provider job model:

```json
{
  "provider": "fal_seedance",
  "prompt": "shot prompt",
  "start_frame": "input/image.png",
  "end_frame": "input/end.png",
  "reference_assets": [],
  "duration_seconds": 5,
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "generate_audio": true,
  "seed": 1234,
  "timeline": {
    "clip_id": "abc123",
    "start_frame_index": 0,
    "length_frames": 120,
    "frame_rate": 24
  }
}
```

## First Implementation Path

1. Copy `ltx_director.py` to `api_director.py` and reduce the schema to provider/timeline inputs.
2. Copy `js/ltx_director.js` to `js/api_director.js`, register it against `APIDirector`, and keep the timeline UI intact.
3. Add segment status fields to timeline state:
   - `generationStatus`: `idle | queued | running | complete | failed`
   - `provider`
   - `providerJobId`
   - `resultVideoFile`
   - `resultAudioFile`
   - `errorMessage`
4. Add a `Generate Selected` action that submits the selected segment as a provider job.
5. Add backend routes for provider submission/status/result download.
6. Store `FAL_KEY` only in the server environment.
7. When a job completes, download the MP4 to ComfyUI output or input, then update that same segment with the resulting video thumbnail/path.
8. If the returned MP4 has audio, extract or decode audio metadata for the audio lane.

## Known Constraints

- GPL-3.0 applies because this fork reuses upstream code.
- Seedance will not expose LTX-style latents, VAEs, attention maps, or PromptRelay internals.
- Provider controls need a capability map so unsupported controls are hidden or disabled.
- A full timeline export will need ffmpeg or an equivalent assembly path.
