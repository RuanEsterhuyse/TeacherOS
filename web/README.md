# TeacherOS v0.1 Interface

This responsive interface is a separate presentation layer over the existing
TeacherOS Python modules. It does not reimplement curriculum reading, lesson
generation, validation, or renderer prompt creation.

## Start locally

From the repository root, load the normal TeacherOS environment and start the
local API:

```bash
set -a; source .env; set +a
PYTHONPATH=. .venv/bin/python -m app.interface_server
```

In another terminal, start the web interface:

```bash
cd web
npm run dev
```

Open `http://localhost:3000`.

## Verify

```bash
cd web
npm run build
```

After a successful build, run `npm start` alongside the local Python API for a
production-mode interface. Curriculum files and generated lessons remain in
their existing TeacherOS locations.
