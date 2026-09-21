# Repository Guidelines

## Project Overview
Argus Safety Predictor Nano is a lightweight, edge-optimized (specifically for Raspberry Pi 5) real-time target detection system. It captures RTSP and local video streams, performs YOLO object detection on the CPU, and provides a Flask-based Web UI for dynamic configuration and video feed viewing.

## Architecture & Data Flow
The system utilizes a multi-threaded Python architecture to decouple frame capture, inference, and the user interface.
- **Capture**: `src/argus/capture/stream_handler.py` runs a background thread for each RTSP stream, using OpenCV to fetch frames. It places the most recent frame into a thread-safe, size-1 Queue (dropping old frames to ensure low latency).
- **Processing**: The main loop in `src/argus/main.py` continuously pulls frames and routes them to `src/argus/vision/inference_engine.py` (which wraps YOLOv8, heavily optimized for CPU execution).
- **UI & Web Server**: A Flask web server (`src/argus/web/web_ui.py`) runs in a daemon thread. It serves an MJPEG feed and a Jinja2 template for configuration.
- **State Management & Hot Reloading**: `src/argus/core/config_manager.py` polls `config.yaml` for modifications. When changed, the main loop dynamically re-initializes models or streams without downtime. Processed frames are shared with the Flask app via a global variable (`web_ui.LATEST_FRAME`).
- **Logging & Events**: Managed by `src/argus/events/stats_logger.py` and `src/argus/events/event_producer.py`, splitting output into separate performance metrics (CPU/RAM/inference speed), detection event logs, and ARGUS JSONL events.

## Key Directories
- `src/argus/`: Core application package structured by domain:
  - `core/`: Configuration management (`config_manager.py`).
  - `capture/`: RTSP streaming, video handling, and grid composition (`stream_handler.py`, `video_handler.py`, `grid_composer.py`).
  - `vision/`: Inference engine wrapping YOLO and NCNN backends (`inference_engine.py`).
  - `compliance/`: Safety compliance & PPE inspection rule engine (`compliance_engine.py`).
  - `events/`: Event producers, JSONL logging, retention cleanup, and crash handlers (`event_producer.py`, `stats_logger.py`, `retention_cleaner.py`, `diagnostic_collector.py`).
  - `integration/`: UMS synchronization, state polling, failover clients, and issue reporting (`model_sync.py`, `ums_config.py`, `failover_ums_client.py`, `state_poller.py`, `issue_service_client.py`, `report_issue.py`).
  - `web/`: Flask Web UI dashboard, MJPEG & SSE feeds, and Jinja2 templates (`web_ui.py`, `templates/`).
- `tests/`: Hierarchical automated test suite:
  - `unit/`: Unit tests for individual domain components.
  - `integration/`: Integration tests for API, streaming, heartbeat, and persistence.
  - `e2e/`: End-to-end scenarios (compliance, UI save, issue reporting).
  - `fixtures/`: Test fixtures and mock servers (`mock_argus_agent.py`).
  - `data/`: Media clips and static test assets.
- `scripts/`: Diagnostic utilities and manual screenshot generation scripts (`generate_screenshots.py`, `ask_and_report.*`).
- `docs/`: Architecture decision records (`docs/adr/`) and mdBook user manual (`docs/user-manual/`).
- `assets/`: Test video files and persistent binary assets.

## Development Commands
- **Install Dependencies**: 
  ```bash
  pip install -r requirements.txt
  pip install -e .
  ```
- **Run Application**: 
  ```bash
  python main.py
  ```
- **Run Tests**:
  ```bash
  pytest
  ```
- **Access Web UI**: Navigate to `http://<device-ip>:8188`
- **Build/Deploy (PyInstaller)**:
  *Crucial Constraint*: Must be built directly on an ARM64 environment (e.g., Raspberry Pi 5 or ARM64 VM). Cross-compilation from x86/x64 is unsupported and will fail. Build the mdBook user manual before running PyInstaller.
  ```bash
  # 1. Build mdBook user manual
  mdbook build docs/user-manual

  # 2. Package binary with PyInstaller spec (Recommended)
  pyinstaller argus_predictor.spec

  # Or package with onefile CLI:
  pyinstaller --onefile \
              --paths src \
              --add-data "src/argus/web/templates:argus/web/templates" \
              --add-data "templates:templates" \
              --add-data "config.yaml:." \
              --add-data "ums-api-config.json:." \
              --add-data "docs/user-manual/book:docs/user-manual/book" \
              --collect-all ultralytics \
              --collect-all flask \
              --collect-all argus_eventlog \
              --collect-all ums_client \
              --name argus_predictor \
              src/argus/main.py
  ```

## Code Conventions & Common Patterns
- **Concurrency**: Heavy reliance on the `threading` module (using daemon threads and Queues) rather than `asyncio` for concurrent operations.
- **Error Handling**: Resilient polling and auto-reconnection for streams. For example, `StreamHandler` tracks failure counts and automatically attempts reconnection to RTSP sources after 10 consecutive failures.
- **State Management**: Uses shared global state (like `web_ui.LATEST_FRAME`) for cross-thread data sharing between the inference loop and the web server. Configuration state is hot-reloaded via file modification polling.
- **Naming Conventions**: Standard Python PEP-8 (PascalCase for classes, snake_case for functions and variables).

## Important Files
- `main.py`: The lightweight root entrypoint delegating to `argus.main:main`.
- `src/argus/main.py`: The core orchestrator managing threads, the inference loop, and config reloading.
- `config.yaml`: The central configuration file detailing model paths, RTSP sources, thresholds, and limits.
- `src/argus/core/config_manager.py`: Parses and polls the YAML configuration for real-time updates.
- `src/argus/vision/inference_engine.py`: YOLO wrapper enforcing CPU-bound execution and formatting bounding boxes.
- `src/argus/capture/stream_handler.py`: Manages RTSP stream connections and low-latency queuing.
- `src/argus/web/web_ui.py`: Flask application providing the configuration dashboard and MJPEG streams.
- `src/argus/events/stats_logger.py`: Dual-logger utility tracking system performance and detections.
- `src/argus/compliance/compliance_engine.py`: Evaluates PPE safety and composite violation rules.
- `argus_predictor.spec`: PyInstaller build specification configured for `src/` layout.

## Runtime/Tooling Preferences
- **Runtime**: Python 3.
- **Hardware Constraint**: Optimized for CPU execution on ARM64 architectures (specifically Raspberry Pi 5).
- **Dependencies**: Uses `opencv-python-headless` to avoid GUI dependencies on headless servers, alongside `ultralytics` (YOLO), `flask`, and `pyyaml`.
- **Deployment**: Distributed as a single binary via `pyinstaller`. At runtime, the binary strictly expects `config.yaml` and the target model file (`.pt`) to reside in the same working directory.

## Testing & QA
- **Frameworks**: `pytest`.
- **Status**: Complete automated test coverage across unit, integration, and E2E tiers under `tests/`.
- **Watchdog & Teardown**: Managed via `tests/conftest.py` with automatic resource teardown fixtures and a 5-second watchdog timer preventing hanging threads on exit.
- **Running Tests**: Run `pytest` for all tests, or `pytest tests/unit/` for fast unit tests.

## Agent skills

### Issue tracker
Gitea server (`guy.mai/safty-predictor-nano` via `tea` CLI). See `docs/agents/issue-tracker.md`. Local specs and archives reside under `.scratch/<feature-slug>/`.

### Triage labels
Default five canonical roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs
Single-context (`AGENTS.md` + `docs/adr/`). See `docs/agents/domain.md`.

