# LLSS Admin API Documentation

## Overview

The Low Level Screen Service (LLSS) Admin API provides endpoints for managing the complete lifecycle of HLSS (High Level Screen Service) instances and their assignment to physical e-Ink devices.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Physical       │     │      LLSS       │     │      HLSS       │
│  Device         │◄───►│  (This Service) │◄───►│  (App Backend)  │
│  (ESP32)        │     │                 │     │  e.g. Lichess   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        │  Polls for frames     │  Manages lifecycle    │
        │  Sends button events  │  Initializes HLSS     │
        │                       │  Forwards inputs      │
        │                       │  Stores frames        │
```

### Key Concepts

- **HLSS Type**: A registered HLSS backend (e.g., "lichess", "homeassistant"). Defines the base URL and default display settings.
- **Instance**: A specific HLSS instance created from an HLSS type. Each instance has its own state, credentials, and can be assigned to devices.
- **Device**: A physical e-Ink display (ESP32-based) that polls LLSS for frames and sends button events.
- **Assignment**: The mapping between devices and instances. A device can have multiple assigned instances and switch between them.

## Usage Flow

### 1. Register an HLSS Type

Before creating instances, you must register the HLSS backend type. This is typically done once per HLSS application.

```http
POST /admin/hlss-types
Content-Type: application/json

{
  "type_id": "lichess",
  "name": "Lichess Chess",
  "base_url": "https://lichess-hlss.example.com/api",
  "auth_token": "secret-token-for-llss-to-authenticate",
  "description": "Play chess on Lichess",
  "default_width": 800,
  "default_height": 480,
  "default_bit_depth": 4
}
```

### 2. Create an Instance

Create an instance of the HLSS type. This represents a specific "screen" or "application session".

```http
POST /admin/instances
Content-Type: application/json

{
  "name": "Living Room Chess",
  "hlss_type_id": "lichess",
  "auto_initialize": true
}
```

When `auto_initialize` is `true`, LLSS immediately calls the HLSS backend's `/instances/init` endpoint to establish trust and exchange callback URLs.

### 3. Handle Configuration (if needed)

After initialization, check the instance status:

```http
GET /admin/instances/{instance_id}
```

If `needs_configuration` is `true`, the response includes a `configuration_url`. Direct the user to this URL to complete setup (e.g., authenticate with Lichess).

### 4. Wait for Device Registration

Devices register themselves with LLSS:

```http
POST /devices/register
Content-Type: application/json

{
  "hardware_id": "ESP32_ABC123",
  "firmware_version": "1.0.0",
  "display": {
    "width": 800,
    "height": 480,
    "bit_depth": 4,
    "partial_refresh": true
  }
}
```

### 5. Assign Instance to Device

Once both instance and device exist, assign the instance to the device:

```http
POST /admin/devices/{device_id}/assign-instance
Content-Type: application/json

{
  "device_id": "dev_abc123",
  "instance_id": "inst_xyz789"
}
```

The first assigned instance automatically becomes the active instance.

### 6. Normal Operation

From this point:
1. The device polls `/devices/{device_id}/state` for actions
2. HLSS renders frames and submits them via `/instances/{instance_id}/frames`
3. LLSS notifies the device of new frames
4. The device fetches frames via `/devices/{device_id}/frames/{frame_id}`
5. Button presses are sent via `/devices/{device_id}/inputs`
6. LLSS forwards inputs to the active HLSS instance
7. HL_LEFT/HL_RIGHT buttons switch between assigned instances

---

## Admin API Reference

### HLSS Type Management

#### List HLSS Types
```http
GET /admin/hlss-types
GET /admin/hlss-types?active_only=true
```

Returns all registered HLSS types.

#### Create HLSS Type
```http
POST /admin/hlss-types
Content-Type: application/json

{
  "type_id": "string",        // Required: unique identifier (e.g., "lichess")
  "name": "string",           // Required: human-readable name
  "base_url": "string",       // Required: HLSS API base URL
  "auth_token": "string",     // Optional: token for LLSS→HLSS auth
  "description": "string",    // Optional: description
  "default_width": 800,       // Optional: default display width
  "default_height": 480,      // Optional: default display height
  "default_bit_depth": 4      // Optional: default bit depth
}
```

#### Get HLSS Type
```http
GET /admin/hlss-types/{type_id}
```

#### Update HLSS Type
```http
PATCH /admin/hlss-types/{type_id}
Content-Type: application/json

{
  "name": "string",           // Optional
  "base_url": "string",       // Optional
  "auth_token": "string",     // Optional
  "description": "string",    // Optional
  "default_width": 800,       // Optional
  "default_height": 480,      // Optional
  "default_bit_depth": 4,     // Optional
  "is_active": true           // Optional: disable/enable type
}
```

#### Delete HLSS Type
```http
DELETE /admin/hlss-types/{type_id}
```

Fails if instances exist using this type.

---

### Instance Management

#### List Instances
```http
GET /admin/instances
GET /admin/instances?hlss_type_id=lichess
```

#### Create Instance
```http
POST /admin/instances
Content-Type: application/json

{
  "name": "string",           // Required: instance name
  "hlss_type_id": "string",   // Required: HLSS type to use
  "display_width": 800,       // Optional: override default width
  "display_height": 480,      // Optional: override default height
  "display_bit_depth": 4,     // Optional: override default bit depth
  "auto_initialize": true     // Optional: auto-init with HLSS (default: true)
}
```

**Response includes:**
- `instance_id`: Unique instance identifier
- `access_token`: Token for HLSS to authenticate with LLSS
- `hlss_initialized`: Whether initialization succeeded
- `hlss_ready`: Whether instance is fully operational
- `needs_configuration`: Whether user configuration is needed
- `configuration_url`: URL for user configuration (if needed)

#### Get Instance
```http
GET /admin/instances/{instance_id}
```

#### Update Instance
```http
PATCH /admin/instances/{instance_id}
Content-Type: application/json

{
  "name": "string",           // Optional
  "display_width": 800,       // Optional
  "display_height": 480,      // Optional
  "display_bit_depth": 4      // Optional
}
```

#### Delete Instance
```http
DELETE /admin/instances/{instance_id}
```

Removes the instance and all device assignments.

#### Initialize Instance
```http
POST /admin/instances/{instance_id}/initialize
```

Manually trigger HLSS initialization. Use this if auto-initialization failed or to re-establish connection.

**What happens during initialization:**
1. LLSS calls HLSS `/instances/init` with:
   - `instance_id`: The instance identifier
   - `callbacks`: URLs for HLSS to submit frames, receive inputs, notify changes
   - `display`: Display capabilities (width, height, bit_depth)
2. HLSS responds with initialization status and optional configuration URL
3. LLSS updates instance state accordingly

#### Refresh Instance Status
```http
POST /admin/instances/{instance_id}/refresh-status
```

Query HLSS for current instance status. Updates `ready`, `needs_configuration`, and `configuration_url`.

---

### Device Management

#### List Devices
```http
GET /admin/devices
```

Returns all devices with their assigned instances.

#### Get Device
```http
GET /admin/devices/{device_id}
```

#### Assign Instance to Device
```http
POST /admin/devices/{device_id}/assign-instance
Content-Type: application/json

{
  "device_id": "string",      // Required
  "instance_id": "string"     // Required
}
```

#### Unassign Instance from Device
```http
DELETE /admin/devices/{device_id}/instances/{instance_id}
```

#### Set Active Instance
```http
POST /admin/devices/{device_id}/set-active-instance?instance_id={instance_id}
```

---

### System Status

#### Get System Status
```http
GET /admin/status
```

**Response:**
```json
{
  "status": "healthy",
  "statistics": {
    "devices": 5,
    "instances": {
      "total": 10,
      "ready": 8,
      "pending_initialization": 1,
      "needs_configuration": 1
    },
    "hlss_types": 3
  }
}
```

---

## Web Dashboard

Access the admin web interface at:

```
GET /admin
```

The dashboard provides:
- **Statistics Overview**: Device count, instance status, HLSS types
- **HLSS Types Tab**: Register and manage HLSS backends
- **Instances Tab**: Create, initialize, and manage instances
- **Devices Tab**: View devices and assign instances

---

## HLSS Backend Requirements

For an HLSS backend to work with LLSS, it must implement:

### Required Endpoints

#### POST /instances/init
Initialize a new instance.

**Request:**
```json
{
  "instance_id": "inst_abc123",
  "callbacks": {
    "frames": "https://llss.example.com/instances/inst_abc123/frames",
    "inputs": "https://llss.example.com/instances/inst_abc123/inputs",
    "notify": "https://llss.example.com/instances/inst_abc123/notify"
  },
  "display": {
    "width": 800,
    "height": 480,
    "bit_depth": 4
  }
}
```

**Response:**
```json
{
  "status": "initialized",
  "needs_configuration": true,
  "configuration_url": "https://hlss.example.com/configure/abc123"
}
```

#### GET /instances/{instance_id}/status
Get instance status.

**Response:**
```json
{
  "instance_id": "inst_abc123",
  "ready": true,
  "needs_configuration": false,
  "configuration_url": null,
  "active_screen": "game_123"
}
```

#### POST /instances/{instance_id}/inputs
Receive forwarded input events.

**Request:**
```json
{
  "button": "BTN_1",
  "event_type": "PRESS",
  "timestamp": "2026-01-14T12:00:00Z"
}
```

#### POST /instances/{instance_id}/render (optional)
Force a new frame render.

### HLSS → LLSS Communication

HLSS uses the callback URLs to:

1. **Submit frames**: `POST {callbacks.frames}` with PNG image
2. **Notify changes**: `POST {callbacks.notify}` when state changes

HLSS must authenticate using the `access_token` returned during instance creation.

---

## Button Types

Devices can send these button events:

| Button | Description |
|--------|-------------|
| `BTN_1` - `BTN_8` | Application-specific buttons |
| `ENTER` | Confirm/Select |
| `ESC` | Cancel/Back |
| `HL_LEFT` | Switch to previous instance (handled by LLSS) |
| `HL_RIGHT` | Switch to next instance (handled by LLSS) |

`HL_LEFT` and `HL_RIGHT` are handled by LLSS for screen switching and are not forwarded to HLSS.

---

## Instance Lifecycle States

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────┐
│ Created  │────►│ Initializing │────►│ Needs Config │────►│ Ready │
│ (pending)│     │              │     │              │     │       │
└──────────┘     └──────────────┘     └──────────────┘     └───────┘
                        │                                       │
                        │ (if no config needed)                 │
                        └───────────────────────────────────────┘
```

- **Pending**: Instance created but not initialized with HLSS
- **Initializing**: Initialization in progress
- **Needs Config**: HLSS requires user configuration (OAuth, settings, etc.)
- **Ready**: Fully operational, can be assigned to devices
