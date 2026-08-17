# Repository Guidelines

## Project Overview
Argus Safety Predictor Nano is a lightweight, edge-optimized (specifically for Raspberry Pi 5) real-time target detection system. It captures RTSP and local video streams, performs YOLO object detection on the CPU, and provides a Flask-based Web UI for dynamic configuration and video feed viewing.

## Architecture & Data Flow
The system utilizes a multi-threaded Python architecture to decouple frame capture, inference, and the user interface.
- **Capture**: `stream_handler.py` runs a background thread for each RTSP stream, using OpenCV to fetch frames. It places the most recent frame into a thread-safe, size-1 Queue (dropping old frames to ensure low latency).
- **Processing**: The main loop in `main.py` continuously pulls frames and routes them to the `inference_engine.py` (which wraps YOLOv8, heavily optimized for CPU execution).
- **UI & Web Server**: A Flask web server (`web_ui.py`) runs in a daemon thread. It serves an MJPEG feed and a Jinja2 template for configuration.
- **State Management & Hot Reloading**: `config_manager.py` polls `config.yaml` for modifications. When changed, the main loop dynamically re-initializes models or streams without downtime. Processed frames are shared with the Flask app via a global variable (`web_ui.LATEST_FRAME`).
- **Logging**: Managed by `stats_logger.py`, splitting output into separate performance metrics (CPU/RAM/inference speed) and detection event logs.

## Key Directories
- `/` (Root): Contains all core Python modules, configuration files, and build manifests.
- `templates/`: Contains Jinja2 HTML templates (e.g., `index.html`) used by the Flask Web UI.

## Development Commands
- **Install Dependencies**: 
  ```bash
  pip install -r requirements.txt
  ```
- **Run Application**: 
  ```bash
  python main.py
  ```
- **Access Web UI**: Navigate to `http://<device-ip>:8188`
- **Build/Deploy (PyInstaller)**:
  *Crucial Constraint*: Must be built directly on an ARM64 environment (e.g., Raspberry Pi 5 or ARM64 VM). Cross-compilation from x86/x64 is unsupported and will fail.
  ```bash
  pyinstaller --onefile \
              --add-data "templates:templates" \
              --add-data "config.yaml:." \
              --collect-all ultralytics \
              --collect-all flask \
              --name argus_predictor \
              main.py
  ```

## Code Conventions & Common Patterns
- **Concurrency**: Heavy reliance on the `threading` module (using daemon threads and Queues) rather than `asyncio` for concurrent operations.
- **Error Handling**: Resilient polling and auto-reconnection for streams. For example, `StreamHandler` tracks failure counts and automatically attempts reconnection to RTSP sources after 10 consecutive failures.
- **State Management**: Uses shared global state (like `web_ui.LATEST_FRAME`) for cross-thread data sharing between the inference loop and the web server. Configuration state is hot-reloaded via file modification polling.
- **Naming Conventions**: Standard Python PEP-8 (PascalCase for classes, snake_case for functions and variables).

## Important Files
- `main.py`: The core orchestrator managing threads, the inference loop, and config reloading.
- `config.yaml`: The central configuration file detailing model paths, RTSP sources, thresholds, and limits.
- `config_manager.py`: Parses and polls the YAML configuration for real-time updates.
- `inference_engine.py`: YOLO wrapper enforcing CPU-bound execution and formatting bounding boxes.
- `stream_handler.py`: Manages RTSP stream connections and low-latency queuing.
- `web_ui.py`: Flask application providing the configuration dashboard and MJPEG streams.
- `stats_logger.py`: Dual-logger utility tracking system performance and detections.
- `templates/index.html`: The frontend UI template.

## Runtime/Tooling Preferences
- **Runtime**: Python 3.
- **Hardware Constraint**: Optimized for CPU execution on ARM64 architectures (specifically Raspberry Pi 5).
- **Dependencies**: Uses `opencv-python-headless` to avoid GUI dependencies on headless servers, alongside `ultralytics` (YOLO), `flask`, and `pyyaml`.
- **Deployment**: Distributed as a single binary via `pyinstaller`. At runtime, the binary strictly expects `config.yaml` and the target model file (`.pt`) to reside in the same working directory.

## Testing & QA
- **Frameworks**: None.
- **Status**: The repository currently lacks automated testing frameworks, test scripts, or a dedicated `tests/` directory. Testing is presumed to be manual via the Web UI and log verification.

## Agent skills

### Issue tracker
Gitea server (`guy.mai/safty-predictor-nano` via `tea` CLI). See `docs/agents/issue-tracker.md`. Local specs and archives reside under `.scratch/<feature-slug>/`.

### Triage labels
Default five canonical roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs
Single-context (`AGENTS.md` + `docs/adr/`). See `docs/agents/domain.md`.

