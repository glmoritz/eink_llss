"""
Debug routes - Device emulator for testing
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Device, DeviceInstanceMap, Frame, Instance

router = APIRouter(prefix="/debug", tags=["Debug"])


@router.get("", response_class=HTMLResponse)
async def debug_emulator(request: Request) -> HTMLResponse:
    """
    Serve the device emulator debug page.

    Provides an interactive UI to emulate a physical e-Ink device
    with all buttons and screen display.
    """
    base_url = str(request.base_url).rstrip("/")

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLSS Device Emulator</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            color: #eee;
        }}
        
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        
        h1 {{
            text-align: center;
            color: #00d9ff;
            margin-bottom: 20px;
            font-size: 1.8rem;
        }}
        
        .device-selector {{
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
        }}
        
        .device-selector label {{
            display: block;
            margin-bottom: 8px;
            color: #aaa;
            font-size: 0.9rem;
        }}
        
        .device-selector select {{
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            background: #2a2a4a;
            color: #fff;
            font-size: 1rem;
            cursor: pointer;
        }}
        
        .device-selector select:focus {{
            outline: 2px solid #00d9ff;
        }}
        
        .refresh-btn {{
            margin-top: 10px;
            padding: 8px 16px;
            background: #00d9ff;
            color: #1a1a2e;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }}
        
        .refresh-btn:hover {{
            background: #00b8d4;
        }}
        
        .device-info {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 0.85rem;
            color: #888;
        }}
        
        .device-info span {{
            color: #00d9ff;
        }}
        
        /* Device Emulator */
        .emulator {{
            background: #2d2d2d;
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1);
            position: relative;
        }}
        
        .emulator-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }}
        
        /* Context buttons (top left) */
        .context-buttons {{
            display: flex;
            gap: 8px;
        }}
        
        .context-btn {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(145deg, #3a3a3a, #252525);
            color: #888;
            font-size: 0.7rem;
            cursor: pointer;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.3), -1px -1px 3px rgba(255,255,255,0.05);
            transition: all 0.1s;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .context-btn:hover {{
            background: linear-gradient(145deg, #454545, #2a2a2a);
            color: #00d9ff;
        }}
        
        .context-btn:active {{
            box-shadow: inset 2px 2px 5px rgba(0,0,0,0.3);
            transform: scale(0.95);
        }}
        
        /* Navigation buttons (top right) */
        .nav-buttons {{
            display: flex;
            gap: 8px;
        }}
        
        .nav-btn {{
            width: 50px;
            height: 40px;
            border-radius: 8px;
            border: none;
            font-size: 0.75rem;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.3), -1px -1px 3px rgba(255,255,255,0.05);
            transition: all 0.1s;
        }}
        
        .nav-btn.esc {{
            background: linear-gradient(145deg, #c0392b, #922b21);
            color: #fff;
        }}
        
        .nav-btn.enter {{
            background: linear-gradient(145deg, #27ae60, #1e8449);
            color: #fff;
        }}
        
        .nav-btn:hover {{
            filter: brightness(1.1);
        }}
        
        .nav-btn:active {{
            box-shadow: inset 2px 2px 5px rgba(0,0,0,0.3);
            transform: scale(0.95);
        }}
        
        /* Screen */
        .screen-container {{
            background: #1a1a1a;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 20px;
        }}
        
        .screen {{
            width: 100%;
            aspect-ratio: 4/3;
            background: #e8e4d9;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }}
        
        .screen img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            image-rendering: pixelated;
        }}
        
        .screen .no-frame {{
            color: #666;
            font-size: 0.9rem;
            text-align: center;
        }}
        
        .screen .no-frame small {{
            display: block;
            margin-top: 5px;
            color: #999;
            font-size: 0.75rem;
        }}
        
        /* Bottom buttons */
        .bottom-buttons {{
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            gap: 8px;
        }}
        
        .bottom-btn {{
            aspect-ratio: 1;
            border-radius: 8px;
            border: none;
            background: linear-gradient(145deg, #3a3a3a, #252525);
            color: #aaa;
            font-size: 0.8rem;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 3px 3px 8px rgba(0,0,0,0.4), -2px -2px 6px rgba(255,255,255,0.05);
            transition: all 0.1s;
        }}
        
        .bottom-btn:hover {{
            background: linear-gradient(145deg, #454545, #2a2a2a);
            color: #00d9ff;
        }}
        
        .bottom-btn:active {{
            box-shadow: inset 3px 3px 8px rgba(0,0,0,0.4);
            transform: scale(0.95);
            background: linear-gradient(145deg, #252525, #3a3a3a);
        }}
        
        /* Status */
        .status {{
            margin-top: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.8rem;
            max-height: 200px;
            overflow-y: auto;
        }}
        
        .status-line {{
            margin: 4px 0;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        
        .status-line.info {{
            color: #00d9ff;
        }}
        
        .status-line.success {{
            color: #2ecc71;
            background: rgba(46, 204, 113, 0.1);
        }}
        
        .status-line.error {{
            color: #e74c3c;
            background: rgba(231, 76, 60, 0.1);
        }}
        
        .status-line.event {{
            color: #f39c12;
        }}
        
        /* No device state */
        .no-device {{
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }}
        
        .no-device h3 {{
            color: #888;
            margin-bottom: 10px;
        }}
        
        /* Register device button */
        .register-section {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }}
        
        .register-btn {{
            width: 100%;
            padding: 12px;
            background: linear-gradient(145deg, #9b59b6, #8e44ad);
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            font-weight: bold;
        }}
        
        .register-btn:hover {{
            background: linear-gradient(145deg, #a569bd, #9b59b6);
        }}
        
        .register-form {{
            display: none;
            margin-top: 15px;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
        }}
        
        .register-form.active {{
            display: block;
        }}
        
        .register-form input {{
            width: 100%;
            padding: 10px;
            margin-bottom: 10px;
            border: none;
            border-radius: 6px;
            background: #2a2a4a;
            color: #fff;
        }}
        
        .register-form .form-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        
        .register-form button {{
            width: 100%;
            padding: 10px;
            background: #27ae60;
            color: #fff;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }}
        
        .hidden {{
            display: none;
        }}
        
        /* Test panel */
        .test-panel {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 12px;
            margin-top: 15px;
        }}
        
        .test-panel h3 {{
            margin: 0 0 15px 0;
            color: #f39c12;
            font-size: 1rem;
        }}
        
        .test-section {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        
        .test-section label {{
            color: #aaa;
            font-size: 0.85rem;
        }}
        
        .test-section input[type="file"] {{
            flex: 1;
            min-width: 200px;
            padding: 8px;
            background: #2a2a4a;
            border: 1px solid #444;
            border-radius: 6px;
            color: #fff;
        }}
        
        .test-section button {{
            padding: 8px 16px;
            background: #f39c12;
            color: #1a1a2e;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }}
        
        .test-section button:hover {{
            background: #e67e22;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ LLSS Device Emulator</h1>
        
        <div class="device-selector">
            <label for="device-select">Select Device:</label>
            <select id="device-select">
                <option value="">-- Select a device --</option>
            </select>
            <button class="refresh-btn" onclick="loadDevices()">🔄 Refresh List</button>
            
            <div id="device-info" class="device-info hidden">
                <div><strong>Device ID:</strong> <span id="info-device-id">-</span></div>
                <div><strong>Hardware ID:</strong> <span id="info-hardware-id">-</span></div>
                <div><strong>Display:</strong> <span id="info-display">-</span></div>
                <div><strong>Firmware:</strong> <span id="info-firmware">-</span></div>
            </div>
            
            <div class="register-section">
                <button class="register-btn" onclick="toggleRegisterForm()">+ Register New Device</button>
                <div id="register-form" class="register-form">
                    <input type="text" id="reg-hardware-id" placeholder="Hardware ID (e.g., ESP32-ABC123)">
                    <input type="text" id="reg-firmware" placeholder="Firmware Version (e.g., 1.0.0)">
                    <div class="form-row">
                        <input type="number" id="reg-width" placeholder="Width (e.g., 800)" value="800">
                        <input type="number" id="reg-height" placeholder="Height (e.g., 600)" value="600">
                    </div>
                    <div class="form-row">
                        <input type="number" id="reg-bit-depth" placeholder="Bit Depth" value="4">
                        <select id="reg-partial">
                            <option value="false">No Partial Refresh</option>
                            <option value="true">Partial Refresh</option>
                        </select>
                    </div>
                    <button onclick="registerDevice()">Register Device</button>
                </div>
            </div>
        </div>
        
        <div id="emulator-container">
            <div class="no-device">
                <h3>No Device Selected</h3>
                <p>Select a device from the dropdown above or register a new one.</p>
            </div>
        </div>
        
        <div class="status" id="status">
            <div class="status-line info">[System] Device emulator ready</div>
        </div>
    </div>
    
    <script>
        const BASE_URL = '{base_url}';
        let currentDevice = null;
        let currentToken = null;
        let pollInterval = null;
        
        // Button mappings
        const BUTTONS = {{
            BTN_1: 'BTN_1', BTN_2: 'BTN_2', BTN_3: 'BTN_3', BTN_4: 'BTN_4',
            BTN_5: 'BTN_5', BTN_6: 'BTN_6', BTN_7: 'BTN_7', BTN_8: 'BTN_8',
            ENTER: 'ENTER', ESC: 'ESC',
            HL_LEFT: 'HL_LEFT', HL_RIGHT: 'HL_RIGHT'
        }};
        
        async function loadDevices() {{
            try {{
                const resp = await fetch(`${{BASE_URL}}/debug/devices`);
                const devices = await resp.json();
                
                const select = document.getElementById('device-select');
                const currentValue = select.value;
                
                select.innerHTML = '<option value="">-- Select a device --</option>';
                
                devices.forEach(device => {{
                    const option = document.createElement('option');
                    option.value = device.device_id;
                    option.textContent = `${{device.hardware_id}} (${{device.device_id}})`;
                    option.dataset.device = JSON.stringify(device);
                    select.appendChild(option);
                }});
                
                if (currentValue && devices.some(d => d.device_id === currentValue)) {{
                    select.value = currentValue;
                }}
                
                log('info', `Loaded ${{devices.length}} device(s)`);
            }} catch (err) {{
                log('error', `Failed to load devices: ${{err.message}}`);
            }}
        }}
        
        function selectDevice() {{
            const select = document.getElementById('device-select');
            const selectedOption = select.selectedOptions[0];
            
            if (!select.value) {{
                showNoDevice();
                return;
            }}
            
            currentDevice = JSON.parse(selectedOption.dataset.device);
            currentToken = currentDevice.access_token;
            
            // Update device info
            document.getElementById('device-info').classList.remove('hidden');
            document.getElementById('info-device-id').textContent = currentDevice.device_id;
            document.getElementById('info-hardware-id').textContent = currentDevice.hardware_id;
            document.getElementById('info-display').textContent = 
                `${{currentDevice.display.width}}x${{currentDevice.display.height}} @ ${{currentDevice.display.bit_depth}}bpp`;
            document.getElementById('info-firmware').textContent = currentDevice.firmware_version;
            
            showEmulator();
            startPolling();
            log('success', `Selected device: ${{currentDevice.hardware_id}}`);
        }}
        
        function showNoDevice() {{
            currentDevice = null;
            currentToken = null;
            stopPolling();
            
            document.getElementById('device-info').classList.add('hidden');
            document.getElementById('emulator-container').innerHTML = `
                <div class="no-device">
                    <h3>No Device Selected</h3>
                    <p>Select a device from the dropdown above or register a new one.</p>
                </div>
            `;
        }}
        
        function showEmulator() {{
            document.getElementById('emulator-container').innerHTML = `
                <div class="emulator">
                    <div class="emulator-header">
                        <div class="context-buttons">
                            <button class="context-btn" onclick="sendButton('HL_LEFT')" title="Context Left">◀</button>
                            <button class="context-btn" onclick="sendButton('HL_RIGHT')" title="Context Right">▶</button>
                        </div>
                        <div class="nav-buttons">
                            <button class="nav-btn esc" onclick="sendButton('ESC')">ESC</button>
                            <button class="nav-btn enter" onclick="sendButton('ENTER')">ENT</button>
                        </div>
                    </div>
                    
                    <div class="screen-container">
                        <div class="screen" id="screen">
                            <div class="no-frame">
                                No frame available
                                <small>Waiting for HLSS to submit a frame...</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bottom-buttons">
                        <button class="bottom-btn" onclick="sendButton('BTN_1')">1</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_2')">2</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_3')">3</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_4')">4</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_5')">5</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_6')">6</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_7')">7</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_8')">8</button>
                    </div>
                </div>
                
                <div class="test-panel">
                    <h3>🧪 Test Tools</h3>
                    <div class="test-section">
                        <label>Upload Test Frame (PNG):</label>
                        <input type="file" id="test-frame-file" accept="image/png,image/jpeg,image/*">
                        <button onclick="uploadTestFrame()">Upload Frame</button>
                    </div>
                </div>
            `;
            
            // Fetch current frame
            fetchFrame();
        }}
        
        async function uploadTestFrame() {{
            if (!currentDevice) {{
                log('error', 'No device selected');
                return;
            }}
            
            const fileInput = document.getElementById('test-frame-file');
            if (!fileInput.files || !fileInput.files[0]) {{
                log('error', 'Please select a file first');
                return;
            }}
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            try {{
                const resp = await fetch(
                    `${{BASE_URL}}/debug/devices/${{currentDevice.device_id}}/test-frame`,
                    {{
                        method: 'POST',
                        body: formData
                    }}
                );
                
                if (resp.ok) {{
                    const result = await resp.json();
                    log('success', `Test frame uploaded: ${{result.frame_id}}`);
                    fetchFrame();
                }} else {{
                    log('error', `Failed to upload frame: ${{resp.status}}`);
                }}
            }} catch (err) {{
                log('error', `Upload error: ${{err.message}}`);
            }}
        }}
        
        async function sendButton(button) {{
            if (!currentDevice || !currentToken) {{
                log('error', 'No device selected');
                return;
            }}
            
            const event = {{
                button: button,
                event_type: 'PRESS',
                timestamp: new Date().toISOString()
            }};
            
            log('event', `Button pressed: ${{button}}`);
            
            try {{
                const resp = await fetch(
                    `${{BASE_URL}}/devices/${{currentDevice.device_id}}/inputs`,
                    {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${{currentToken}}`
                        }},
                        body: JSON.stringify(event)
                    }}
                );
                
                if (resp.ok) {{
                    log('success', `Input event sent: ${{button}}`);
                    // Poll for new frame after button press
                    setTimeout(pollState, 100);
                }} else {{
                    log('error', `Failed to send input: ${{resp.status}}`);
                }}
            }} catch (err) {{
                log('error', `Error sending input: ${{err.message}}`);
            }}
        }}
        
        async function pollState() {{
            if (!currentDevice || !currentToken) return;
            
            try {{
                const resp = await fetch(
                    `${{BASE_URL}}/devices/${{currentDevice.device_id}}/state`,
                    {{
                        headers: {{
                            'Authorization': `Bearer ${{currentToken}}`
                        }}
                    }}
                );
                
                if (resp.ok) {{
                    const state = await resp.json();
                    
                    if (state.action === 'FETCH_FRAME' && state.frame_id) {{
                        log('info', `New frame available: ${{state.frame_id}}`);
                        await fetchFrameById(state.frame_id);
                    }}
                }}
            }} catch (err) {{
                // Silent fail for polling
            }}
        }}
        
        async function fetchFrame() {{
            if (!currentDevice || !currentToken) return;
            
            try {{
                // Try to get current frame from debug endpoint
                const resp = await fetch(
                    `${{BASE_URL}}/debug/devices/${{currentDevice.device_id}}/frame`,
                    {{
                        headers: {{
                            'Authorization': `Bearer ${{currentToken}}`
                        }}
                    }}
                );
                
                if (resp.ok) {{
                    const blob = await resp.blob();
                    if (blob.size > 0) {{
                        const url = URL.createObjectURL(blob);
                        document.getElementById('screen').innerHTML = `<img src="${{url}}" alt="Device Frame">`;
                        log('success', 'Frame loaded');
                    }}
                }}
            }} catch (err) {{
                // Frame not available yet
            }}
        }}
        
        async function fetchFrameById(frameId) {{
            if (!currentDevice || !currentToken) return;
            
            try {{
                const resp = await fetch(
                    `${{BASE_URL}}/devices/${{currentDevice.device_id}}/frames/${{frameId}}`,
                    {{
                        headers: {{
                            'Authorization': `Bearer ${{currentToken}}`
                        }}
                    }}
                );
                
                if (resp.ok) {{
                    const blob = await resp.blob();
                    if (blob.size > 0) {{
                        const url = URL.createObjectURL(blob);
                        document.getElementById('screen').innerHTML = `<img src="${{url}}" alt="Device Frame">`;
                        log('success', `Frame ${{frameId}} displayed`);
                    }}
                }}
            }} catch (err) {{
                log('error', `Failed to fetch frame: ${{err.message}}`);
            }}
        }}
        
        function startPolling() {{
            stopPolling();
            pollInterval = setInterval(pollState, 2000);
            pollState();
        }}
        
        function stopPolling() {{
            if (pollInterval) {{
                clearInterval(pollInterval);
                pollInterval = null;
            }}
        }}
        
        function toggleRegisterForm() {{
            const form = document.getElementById('register-form');
            form.classList.toggle('active');
        }}
        
        async function registerDevice() {{
            const hardwareId = document.getElementById('reg-hardware-id').value;
            const firmware = document.getElementById('reg-firmware').value;
            const width = parseInt(document.getElementById('reg-width').value);
            const height = parseInt(document.getElementById('reg-height').value);
            const bitDepth = parseInt(document.getElementById('reg-bit-depth').value);
            const partial = document.getElementById('reg-partial').value === 'true';
            
            if (!hardwareId || !firmware) {{
                log('error', 'Hardware ID and Firmware are required');
                return;
            }}
            
            const registration = {{
                hardware_id: hardwareId,
                firmware_version: firmware,
                display: {{
                    width: width || 800,
                    height: height || 600,
                    bit_depth: bitDepth || 4,
                    partial_refresh: partial
                }}
            }};
            
            try {{
                const resp = await fetch(`${{BASE_URL}}/devices/register`, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify(registration)
                }});
                
                if (resp.ok) {{
                    const result = await resp.json();
                    log('success', `Device registered: ${{result.device_id}}`);
                    
                    // Clear form and close
                    document.getElementById('reg-hardware-id').value = '';
                    document.getElementById('reg-firmware').value = '';
                    document.getElementById('register-form').classList.remove('active');
                    
                    // Reload devices and select the new one
                    await loadDevices();
                    document.getElementById('device-select').value = result.device_id;
                    selectDevice();
                }} else {{
                    const error = await resp.json();
                    log('error', `Registration failed: ${{error.detail || resp.status}}`);
                }}
            }} catch (err) {{
                log('error', `Registration error: ${{err.message}}`);
            }}
        }}
        
        function log(type, message) {{
            const status = document.getElementById('status');
            const time = new Date().toLocaleTimeString();
            const line = document.createElement('div');
            line.className = `status-line ${{type}}`;
            line.textContent = `[${{time}}] ${{message}}`;
            status.appendChild(line);
            status.scrollTop = status.scrollHeight;
            
            // Keep only last 50 messages
            while (status.children.length > 50) {{
                status.removeChild(status.firstChild);
            }}
        }}
        
        // Event listeners
        document.getElementById('device-select').addEventListener('change', selectDevice);
        
        // Initial load
        loadDevices();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@router.get("/devices")
async def list_devices(db: Session = Depends(get_db)) -> list:
    """
    List all registered devices for the debug emulator.
    """
    devices = db.query(Device).all()
    return [device.to_dict() for device in devices]


@router.get("/devices/{device_id}/frame")
async def get_device_current_frame(
    device_id: str,
    db: Session = Depends(get_db),
):
    """
    Get the current frame for a device (for the emulator).
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return Response(content=b"", media_type="application/octet-stream")

    current_frame_id = device.current_frame_id
    if not current_frame_id:
        return Response(content=b"", media_type="application/octet-stream")

    frame = db.query(Frame).filter(Frame.frame_id == current_frame_id).first()
    if not frame or not frame.data:
        return Response(content=b"", media_type="application/octet-stream")

    return Response(content=frame.data, media_type="image/png")


@router.post("/devices/{device_id}/test-frame")
async def upload_test_frame(
    device_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a test frame directly to a device (for testing).
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return {"error": "Device not found"}

    content = await file.read()

    # Generate frame ID
    frame_id = uuid.uuid4()
    frame_hash = hashlib.sha256(content).hexdigest()[:16]

    # Store the frame in database
    frame = Frame(
        frame_id=frame_id,
        data=content,
        hash=frame_hash,
    )
    db.add(frame)

    # Update device
    device.current_frame_id = frame_id
    db.commit()

    return {
        "frame_id": str(frame_id),
        "size": len(content),
        "message": "Test frame uploaded successfully",
    }


@router.post("/devices/{device_id}/link-instance")
async def link_device_to_instance(
    device_id: str,
    instance_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Link a device to an instance (for testing).
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return {"error": "Device not found"}

    # Update device's active instance
    device.active_instance_id = instance_id

    # Also add to mapping table
    existing_map = (
        db.query(DeviceInstanceMap)
        .filter(
            DeviceInstanceMap.device_id == device_id,
            DeviceInstanceMap.instance_id == instance_id,
        )
        .first()
    )

    if not existing_map:
        mapping = DeviceInstanceMap(
            device_id=device_id,
            instance_id=instance_id,
        )
        db.add(mapping)

    db.commit()

    return {
        "device_id": device_id,
        "instance_id": instance_id,
        "message": "Device linked to instance successfully",
    }


@router.get("/instances")
async def list_instances(db: Session = Depends(get_db)):
    """
    List all instances (for the debug interface).
    """
    instances = db.query(Instance).all()
    return [inst.to_dict() for inst in instances]
