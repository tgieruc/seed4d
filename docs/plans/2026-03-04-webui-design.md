# SEED4D Web UI — Design Document

**Date:** 2026-03-04
**Status:** Approved

## Overview

A web application to control the SEED4D data generation pipeline: configuring scenarios, supervising generation jobs, and visualizing output data. Runs on the host machine, controlling CARLA inside Docker.

**Target users:** Lab researchers (intuitive but not consumer-grade).

## Tech Stack

- **Frontend:** React + Vite + TypeScript
- **Backend:** FastAPI (Python, async)
- **Database:** SQLite (via SQLAlchemy)
- **3D Rendering:** Three.js (react-three-fiber)
- **Real-time:** WebSockets (FastAPI native)
- **Styling:** TBD (Tailwind or similar)

## Architecture

```
seed4d/
├── webui/
│   ├── backend/          # FastAPI app
│   │   ├── api/          # REST + WebSocket endpoints
│   │   ├── models/       # SQLAlchemy models + reuse Pydantic from common/config.py
│   │   ├── services/     # Job runner, Docker control, file browser
│   │   └── main.py       # uvicorn entry
│   └── frontend/         # React + Vite + TypeScript
│       └── src/
│           ├── pages/    # ConfigBuilder, JobMonitor, DataViewer
│           └── components/
├── common/               # Existing — shared Pydantic models
├── config/               # Existing — YAML/JSON configs
├── data/                 # Existing — generated output
└── ...
```

```
┌──────────────┐     ┌──────────────────────┐
│  React App   │────▶│   FastAPI Backend     │
│  :5173       │◀────│   :8000               │
│              │ WS  │                       │
│  Pages:      │     │  - REST API           │
│  - Config    │     │  - WebSocket          │
│  - Jobs      │     │  - Job Queue          │
│  - Viewer    │     │  - File Server        │
└──────────────┘     └──────────┬────────────┘
                                │ subprocess
                   ┌────────────▼─────────────┐
                   │  CARLA Docker Container   │
                   │  generator.py (per job)   │
                   │  :2000 (CARLA server)     │
                   └──────────────────────────┘

  ┌─────────────┐   ┌────────────────────────┐
  │  SQLite DB   │   │  data/ (generated)     │
  │  jobs,configs│   │  config/ (scenarios)   │
  └─────────────┘   └────────────────────────┘
```

## API Endpoints

### REST

- `GET/POST /api/configs` — List/create scenario configs
- `GET/PUT/DELETE /api/configs/{id}` — CRUD single config
- `POST /api/configs/{id}/validate` — Validate config via Pydantic
- `GET /api/camera-rigs` — List available camera rig JSONs
- `POST /api/camera-rigs` — Upload/create new camera rig
- `GET /api/maps` — List CARLA towns
- `GET /api/vehicles` — List vehicle blueprints
- `GET /api/weathers` — List weather presets
- `POST /api/jobs` — Submit a generation job
- `GET /api/jobs` — List jobs (filterable by status, map, date)
- `GET /api/jobs/{id}` — Job detail (status, progress, config)
- `POST /api/jobs/{id}/cancel` — Cancel running job
- `POST /api/jobs/{id}/rerun` — Re-run a job
- `GET /api/datasets` — Browse generated data tree
- `GET /api/datasets/{path}/transforms` — Get transforms.json
- `GET /api/datasets/{path}/images/{file}` — Serve image files
- `GET /api/datasets/{path}/pointcloud` — Serve PLY files
- `GET /api/datasets/{path}/bev` — Serve BEV GIFs

### WebSocket

- `WS /ws/jobs/{id}` — Real-time job updates: progress, log lines, thumbnail paths, status changes

## Page 1: Config Builder

**Layout:** Form (left) + 3D Scene Preview (right, always visible)

### Form Sections

1. **World** — Map dropdown (Town01-10), Weather dropdown (13 presets), Vehicle picker (searchable)
2. **Spawn Points** — Multi-select with map preview showing available points
3. **Simulation** — Steps count, min_distance, sync mode, delta seconds
4. **Traffic** — Vehicle count slider, pedestrian count slider, large vehicles toggle, sort spawnpoints toggle
5. **Sensor Datasets** — Add/remove dataset blocks. Each block: name, sensor types (checkboxes), resolution (W×H), FOV, camera rig JSON (upload or pick existing)
6. **Camera Rig Editor** — 3D Three.js view of a car with camera positions you can drag around. Shows FOV cones. Edit pitch/yaw/position per camera
7. **Options** — BEV camera, invisible ego, 3D bounding boxes toggles
8. **Post-processing** — Checkboxes: normalize coords, vehicle masks, combine transforms, map generation
9. **Actions** — "Save Config" (stores to DB + YAML), "Save & Run" (saves + submits job)

Auto-validates using Pydantic models from `common/config.py`.

### 3D Scene Preview Panel

- Car model centered (simple 3D box or low-poly mesh)
- Camera positions as colored frustums with FOV cones
- Spawn points as markers on town grid
- Selected spawn point highlighted
- Updates live as form changes
- Orbit/zoom/pan (OrbitControls)
- Toggle layers: FOV cones, camera labels, spawn points

## Page 2: Job Monitor

### Job List (left/top)

- Table: Status icon, Config name, Map, Weather, Spawn points, Steps, Created, Duration
- Statuses: Queued, Running, Completed, Failed, Cancelled
- Filter bar: by status, map, date range
- Bulk actions: cancel selected, re-run failed
- "New Job" button → links to Config Builder

### Job Detail Panel (right/bottom, opens on click)

- **Header** — Job name, status badge, start/end time, duration
- **Progress** — Overall progress bar (spawn points done / total), current spawn point + step
- **Live Log** — Streaming terminal output via WebSocket, auto-scroll with pause, searchable
- **Config Summary** — Collapsible YAML view
- **Output Preview** — Latest captured RGB thumbnails per camera, updates each timestep
- **Actions** — Cancel, Re-run, Open in Data Viewer, Download config

### Real-time

- Backend wraps `generator.py` subprocess, parses stdout for progress
- WebSocket pushes status changes, log lines, thumbnail paths
- Auto-reconnects on connection drop

## Page 3: Data Viewer

### Dataset Browser Sidebar (left)

- Tree: Map → Weather → Vehicle → Spawn Point
- Completion status badges (green/red)
- Search/filter by map, weather, vehicle
- File size and frame count

### Viewer Area — Three Tabs

#### Tab 1: Image Gallery

- Grid of sensor outputs per timestep: RGB, depth, segmentation, instance segmentation
- Camera selector (dropdown or clickable labels)
- Timestep scrubber/slider
- Click to enlarge, side-by-side compare (e.g. RGB vs depth)

#### Tab 2: 3D Viewer

- Three.js scene:
  - Camera frustums in world space (from transforms.json)
  - Point cloud overlay (from PLY if LiDAR exists)
  - 3D bounding boxes (if generated)
  - Click frustum → floating panel with that camera's RGB image
- Timestep slider for animation
- Toggle layers: cameras, point cloud, bounding boxes, vehicle path

#### Tab 3: BEV / Overview

- BEV GIF playback (BEV_ego.gif)
- Map overlay with vehicle trajectory (positions.json)
- Synced side-by-side: BEV + selected ego camera by timestep

## Database Schema (SQLite)

### configs

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | TEXT | User-given name |
| yaml_content | TEXT | Full YAML string |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### jobs

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| config_id | UUID | FK → configs |
| status | TEXT | queued/running/completed/failed/cancelled |
| progress | JSON | {spawn_point: X, step: Y, total_spawn_points: N, total_steps: M} |
| log | TEXT | Full log output |
| pid | INT | OS process ID (for cancellation) |
| created_at | DATETIME | |
| started_at | DATETIME | |
| completed_at | DATETIME | |
| error | TEXT | Error message if failed |
| data_path | TEXT | Output directory path |

### camera_rigs

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | TEXT | |
| json_content | TEXT | Camera rig JSON |
| created_at | DATETIME | |
