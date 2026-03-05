<h2 align="center">SEED4D: A Synthetic Ego–Exo Dynamic 4D Driving </h2>
<h3 align="center">WACV 2025</h3>

Marius Kästingschäfer and Théo Gieruc and Sebastian Bernhard and Dylan Campbell and Eldar Insafutdinov and Eyvaz Najafli and Thomas Brox 

![Teaser image](docs/media/teaser/overview.png)

## [Project page](https://seed4d.github.io/) | [Paper](https://arxiv.org/abs/2412.00730) | [Data](coming_soon)

Models for egocentric 3D and 4D reconstruction, including few-shot interpolation and extrapolation settings, can benefit from having images from exocentric viewpoints as supervision signals. No existing dataset provides the necessary mixture of complex, dynamic, and multi-view data. To facilitate the development of 3D and 4D reconstruction methods in the autonomous driving context, we propose a Synthetic Ego--Exo Dynamic 4D (SEED4D) dataset. We here provide the code with which we generated the data.

![Sensors](docs/media/teaser/sensors.png)


Our data generator is build on [CARLA](https://github.com/carla-simulator/carla) and can generator synthetic egocentrical views similar to the camera setup in [nuScenes](https://www.nuscenes.org/nuscenes), [KITTI360](https://www.cvlibs.net/datasets/kitti-360/) or [Waymo](https://waymo.com/open/) and simultaneously create create exocentrical views. Resulting poses are outputted in a [Nerfstudio suitable data format](https://docs.nerf.studio/quickstart/data_conventions.html).


![Sensor Overview](docs/media/teaser/sensor_setup.png)


 ## Overview
- [Carla Sanity check](docs/carla_check.md)
- [Dataset creation](docs/datasets.md)
- [Dataset structure](docs/data_structure.md)
- [Dataset visualization](docs/visualizations.md)

## Web UI

A browser-based interface for configuring and running dataset generation jobs without using the command line.

**Demo:** [https://youtu.be/owa3BLJoix4](https://youtu.be/owa3BLJoix4)

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Node.js](https://nodejs.org/) with npm
- Docker with GPU support (`nvidia-container-toolkit`)
- A built `seed4d` Docker image (`docker build -t seed4d .`)

### Running the Web UI

```bash
./webui/dev.sh
```

This starts:
- **Backend** (FastAPI) at `http://localhost:8000`
- **Frontend** (Vite/React) at `http://localhost:5173`
- API docs at `http://localhost:8000/docs`

Open `http://localhost:5173` in your browser.

### Pages

**Config Builder** — Visual editor for YAML scenario configs. Set map, weather, vehicle, spawn points, sensor rigs (cameras and LiDAR), and simulation parameters. Includes a 3D preview of the sensor setup. Save configs to the database for reuse.

**Job Monitor** — Submit saved configs as generation jobs, track progress with live log streaming, cancel running jobs, and re-run completed or failed jobs. Jobs run one at a time by default (each in its own Docker container). Failed containers are kept for inspection; successful ones are removed automatically.

**Data Viewer** — Browse generated datasets. Visualize camera images and 3D point clouds from LiDAR, with camera pose overlays and per-sensor-group filtering.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SEED4D_IMAGE` | `seed4d` | Docker image used for generation jobs |

## Acknowledgements 
We thank the creators of NeRFStudio, and the CARLA simulator for generously open-sourcing their code.

## License
Copyright (C) 2025 co-pace GmbH (subsidiary of Continental AG). All rights reserved. This repository is licensed under the BSD-3-Clause license. See [LICENSE](LICENSE) for the full license text.

## Citation
If you find this code useful, please reference in your paper:
```bibtex
@InProceedings{Kastingschafer_2025_WACV,
    author    = {K\"astingsch\"afer, Marius and Gieruc, Th\'eo and Bernhard, Sebastian and Campbell, Dylan and Insafutdinov, Eldar and Najafli, Eyvaz and Brox, Thomas},
    title     = {SEED4D: A Synthetic Ego-Exo Dynamic 4D Data Generator Driving Dataset and Benchmark},
    booktitle = {Proceedings of the Winter Conference on Applications of Computer Vision (WACV)},
    month     = {February},
    year      = {2025},
    pages     = {7741-7753}
}
```
