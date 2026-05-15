# API Director Handoff

## Why This Exists

The chat transcript is not stored in the local Mac mini project folder. It belongs to the active Codex/ChatGPT session. To make the work visible from the Mac mini environment, this file captures the current state, repo links, and next steps.

## Fork And Local Checkout

- Upstream repo: https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI
- Fork: https://github.com/Matt525/WhatDreamsCost-ComfyUI
- Local checkout: `/Volumes/Codex SSD/Codex/api-director/api-director-comfyui`
- Working branch: `api-director-spike`
- Branch URL: https://github.com/Matt525/WhatDreamsCost-ComfyUI/tree/api-director-spike

## What Was Done

1. Created a GitHub fork under `Matt525`.
2. Cloned the fork locally.
3. Added `upstream` remote pointing back to `WhatDreamsCost/WhatDreamsCost-ComfyUI`.
4. Created branch `api-director-spike`.
5. Added `docs/API_DIRECTOR_SPIKE.md`.
6. Committed and pushed the spike branch.
7. Ran Python syntax compilation across the existing Python node files successfully.

## Main Finding

The UI we care about is mostly in:

- `js/ltx_director.js`

The LTX-specific backend is mostly in:

- `ltx_director.py`

The practical path is to create a parallel `API Director` node that keeps the same timeline/editor UI, but replaces the LTX local-model backend with provider-based generation, starting with fal.ai Seedance.

## Critical Product Behavior

- Generate into a timeline clip.
- Keep generated clips movable and trimmable.
- Preserve the separate audio lane.
- Show pending/running/complete states directly on the clip.
- Return provider-generated videos into the exact timeline slot that requested them.
- Split or expose returned audio separately when possible.

## Next Step

Create a first implementation branch that:

1. Copies `ltx_director.py` to `api_director.py`.
2. Copies `js/ltx_director.js` to `js/api_director.js`.
3. Registers a new `API Director` ComfyUI node.
4. Removes LTX-only model/clip/VAE/latent inputs.
5. Adds provider settings for `fal_seedance`.
6. Adds backend routes for submit/status/download.
7. Stores `FAL_KEY` in the server environment only.

