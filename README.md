# Low Level Screen Service (LLSS)

This repository contains the **specification and reference implementation** of the **Low Level Screen Service (LLSS)** — a cloud-based broker for ultra-thin e-Ink display devices.

LLSS is designed to keep devices as *dumb* as possible. All rendering, layout, state management, and application logic live in the cloud. Devices are reduced to secure network clients that:

* poll for state,
* fetch pre-rendered framebuffer data,
* forward button input events.

The system is built around a clear separation of concerns:

* **LLSS (this project)**
  Owns devices, authentication, frame storage, diffing, partial refresh orchestration, and routing of inputs.

* **HLSS (High Level Screen Services)**
  Independent services (e.g. correspondence chess, Home Assistant dashboards) that generate logical frames and react to user input.

* **Devices**
  ESP32-based e-Ink terminals that render raw framebuffers and expose a small set of abstract buttons.

This repository includes:

* A complete **OpenAPI 3.1 specification** defining the LLSS contract
* A **reference implementation** of the LLSS backend
* Documentation covering architecture, data flow, and design decisions

The project targets **e-Ink displays** with support for partial refresh, server-side rendering (PNG → raw framebuffer), and context-driven input, while remaining extensible to future display technologies.

---

**Key design goals**

* Zero UI or layout logic on the device
* Stateless, poll-based device communication
* Server-side frame diffing and partial refresh
* Pluggable, multi-instance application model (HLSS)
* Long-term maintainability and evolvability

This project is opinionated by design and optimized for reliability, simplicity on embedded hardware, and rapid iteration on the server side.
# eink_llss
Low-level backend for e-Ink terminals with server-side rendering and pluggable applications.
