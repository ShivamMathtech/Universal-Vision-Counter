# Design decisions and extension points

## Concurrency

The interactive engine owns one camera or video source. Reader, inference and renderer are three separate workers. Frames pass through a bounded queue and a latest-frame pointer. Inference results are atomically swapped under a short lock. SQLite writes happen in the inference worker; the renderer never waits for YOLO inference.

The model manager serializes model loads/prediction with a lock. Session starts, stops and model changes have a service-level lock. Stop joins workers before source replacement. The full-video export worker runs while interactive analysis is stopped, preventing simultaneous resets of ByteTrack's ID allocator.

WebSocket connections send metadata only. MJPEG clients share the already-encoded JPEG buffer, so each client does not trigger its own detector or JPEG encoder.

## Persistence

`History` contains SQL access for settings, sessions, tracks, detection observations, events, analytics and uploaded-model records. A track is deduplicated by `(session, track_id)` in the database. Only recent trajectory/state records remain in RAM. CSV and JSON stream records in 500-row pages.

Long-running sessions consume disk space as metadata is saved. There is no automatic destructive retention cleanup. A deployment needing retention policies can add an explicit archive/delete job at this repository boundary.

## Geometry

All boxes, centers, line points and zone vertices use normalized coordinates. The video/image stage preserves source aspect ratio; the drawing overlay uses the same stage. YOLO's output boxes are mapped back to original pixel coordinates before normalization.

Line crossing uses significant centroid positions on opposite sides of a finite directed segment, with a dead band and debounce. Polygon occupancy uses ray casting. New geometry starts a fresh directional state and logs a geometry-reset event.

## Security boundary

This is local, single-user software, with a loopback server and no remote accounts. Uploaded files get generated names and cannot choose destination paths. Model loading permits standard installed network classes through restricted PyTorch deserialization; unknown pickle functions and custom Python classes are rejected. Images have a pixel limit checked before full OpenCV decoding. Upload sizes and API values are bounded.

For a hosted multi-user service, replace local ownership assumptions with authenticated session isolation, upload quotas, dedicated model workers, network controls, TLS and managed retention. These hosted-service capabilities are deliberately outside this local application's scope.

## Future modules

A speed estimator can consume normalized trajectories after camera calibration. Heatmaps and density summaries can consume detection metadata. A new detector or tracker can implement the same result records. Multi-camera support requires one engine and tracker namespace per camera, plus a session-aware frontend and repository. Physical re-identification requires a dedicated embedding/re-ID strategy and evaluation, not just a larger track buffer.
