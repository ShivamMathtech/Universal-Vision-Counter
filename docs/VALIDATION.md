# Release verification

Validated on 2026-10-08 in a Linux execution environment with Python 3.12.14, Node.js 24.19.0, PyTorch 2.14.1 CPU, Ultralytics 8.3.221 and OpenCV 4.11.0.

## Automated checks

**22 tests passed.** The exact pytest output is in `test-results.txt`.

- Same confirmed object ID across 100 observations is counted once.
- Ten initial objects, five departures and three arrivals: 13 unique tracks, 8 currently present.
- Bidirectional finite line crossings, near-line jitter and crossings outside the line endpoints.
- Multiple polygon occupancies, observed zone exits, track-class consistency and bounded trajectories.
- Real ByteTrack: stable identity over 100 sequential frames and low-confidence association.
- Real YOLO11 nano inference on the bundled Ultralytics bus photograph; nonzero detections and dynamic class counts.
- A three-class custom Ultralytics checkpoint (`apple`, `orange`, `banana`) loads its own names. This test creates untrained architecture weights solely to validate checkpoint compatibility; it is not a trained fruit detector.
- A malicious pickle reducer is rejected without executing its payload.
- FastAPI health/settings/validation, local-origin protection, missing-model errors, WebSocket metadata, CSV/JSON and history.
- Real video lifecycle: upload, inference, pause/resume, snapshot, recording, seek into a fresh session, stop, complete annotated-video export, and output frame count.
- A deliberately slow 250 ms inference pass leaves rendering above 15 FPS while queue size stays at or below two packets.

One dependency deprecation warning concerns Starlette's test-client alias for an AnyIO helper. Tests and runtime requests completed successfully.

The TypeScript/Vite production build passed; see `frontend-build.txt`. Python modules compile successfully.

## Browser checks

Headless Chromium exercised the actual React application against its FastAPI server:

- Initial model setup.
- Image upload and visible real detector output: 5 observations in the source photograph.
- Drawing and saving a count line and a four-vertex zone.
- Saved session history.
- Settings rendering and persistent theme changes.
- Video upload, live annotation, pause/resume controls and stop.
- Responsive widths: 1920, 1440, 1366, 1280 and 390 pixels; no horizontal overflow.
- No uncaught JavaScript errors.

See `browser-validation.json` and the screenshots in this directory.

## Measured sample benchmark

The bundled sample photograph was panned to create a six-second, 24-FPS video. A five-second run of the asynchronous pipeline used CPU, 416-pixel inference, a target of 8 inference FPS and a two-frame queue.

The original measurements are in `benchmark.json`:

| Metric | Mean across 10 samples |
|---|---:|
| Reader throughput | 23.89 FPS |
| JPEG render/encode rate | 23.90 FPS |
| Inference rate | 8.42 FPS |
| YOLO inference time | 62.34 ms |
| Capture-to-result latency | 94.59 ms |
| Process RSS | 0.44 GB |

78 stale inference packets were dropped by the final sample, as intended. The queue stayed bounded. Dropped inference packets do not block the independent reader/renderer.

These are measurements on this build environment, **not a promise for every CPU or scene**. A panned still photograph is a functional benchmark, not an accuracy dataset. This run does not establish counting precision/recall, crowd performance, long-duration reliability or real-world re-identification accuracy.

## Hardware-dependent checks not performed

- Physical USB/laptop camera capture and camera drivers.
- Windows startup execution; the scripts were prepared for Python 3.11/3.12 on Windows but executed here on Linux only.
- CUDA inference.
- Docker image build and Docker camera forwarding.
- Browser playback of every possible audio/container codec.
- Day-long runs on an actual 8 GB Windows workstation.

Run the camera workflow locally to verify OS permissions, supported resolutions and achievable FPS. Annotated exports are video-only MJPG/AVI. Count totals are unique tracker IDs within a session; re-entry or association errors can assign a new ID to the same physical object.
