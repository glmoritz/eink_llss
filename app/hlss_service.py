"""
HLSS Service - Server-to-server communication with HLSS backends.

This module handles:
- Initializing HLSS instances
- Checking HLSS instance status
- Forwarding input events to HLSS
- Triggering renders
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from db_models import HLSSType, Instance
from models import (
    DisplayCapabilities,
    HLSSCallbacks,
    HLSSFrameMetadata,
    HLSSFrameSendResponse,
    HLSSInitRequest,
    HLSSInitResponse,
    HLSSStatusResponse,
    InputEvent,
)

logger = logging.getLogger(__name__)


class HLSSService:
    """Service for communicating with HLSS backends."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        """
        Initialize the HLSS service.

        Args:
            base_url: The base URL of the LLSS API (for constructing callbacks).
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get_callbacks(self, instance_id: str) -> HLSSCallbacks:
        """Generate callback URLs for an instance."""
        return HLSSCallbacks(
            frames=f"{self.base_url}/instances/{instance_id}/frames",
            inputs=f"{self.base_url}/instances/{instance_id}/inputs",
            notify=f"{self.base_url}/instances/{instance_id}/notify",
        )

    async def initialize_instance(
        self,
        hlss_type: HLSSType,
        instance: Instance,
        display: DisplayCapabilities,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Initialize an instance with its HLSS backend.

        Calls the HLSS /instances/init endpoint to establish trust and
        provide callback URLs.

        Args:
            hlss_type: The HLSS type configuration.
            instance: The instance to initialize.
            display: Display capabilities for the instance.

        Returns:
            Tuple of (success, configuration_url, error_message)
        """
        init_url = f"{hlss_type.base_url.rstrip('/')}/instances/init"
        callbacks = self._get_callbacks(instance.instance_id)

        request_data = HLSSInitRequest(
            instance_id=instance.instance_id,
            callbacks=callbacks,
            display=display,
        )

        headers = {"Content-Type": "application/json"}
        if hlss_type.auth_token:
            headers["Authorization"] = f"Bearer {hlss_type.auth_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    init_url,
                    json=request_data.model_dump(),
                    headers=headers,
                )

                if response.status_code == 200:
                    data = response.json()
                    init_response = HLSSInitResponse(**data)

                    if init_response.status == "initialized":
                        config_url = (
                            init_response.configuration_url
                            if init_response.needs_configuration
                            else None
                        )
                        return True, config_url, None
                    else:
                        return False, None, f"Unexpected status: {init_response.status}"
                else:
                    return (
                        False,
                        None,
                        f"HLSS returned status {response.status_code}: {response.text}",
                    )

        except httpx.TimeoutException:
            logger.error(
                f"Timeout initializing instance {instance.instance_id} with HLSS"
            )
            return False, None, "Timeout connecting to HLSS backend"
        except httpx.RequestError as e:
            logger.error(f"Error initializing instance {instance.instance_id}: {e}")
            return False, None, f"Connection error: {str(e)}"
        except Exception as e:
            logger.error(
                f"Unexpected error initializing instance {instance.instance_id}: {e}"
            )
            return False, None, f"Unexpected error: {str(e)}"

    async def delete_instance(
        self,
        hlss_type: HLSSType,
        instance_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Notify HLSS that an instance is being deleted.

        Args:
            hlss_type: The HLSS type configuration.
            instance_id: The instance ID to delete.

        Returns:
            Tuple of (success, error_message)
        """
        delete_url = f"{hlss_type.base_url.rstrip('/')}/instances/{instance_id}"

        headers = {}
        if hlss_type.auth_token:
            headers["Authorization"] = f"Bearer {hlss_type.auth_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(delete_url, headers=headers)

                if response.status_code in (200, 204):
                    return True, None
                elif response.status_code == 404:
                    # Instance doesn't exist on HLSS, that's fine
                    return True, None
                else:
                    return False, f"HLSS returned status {response.status_code}"

        except httpx.TimeoutException:
            return False, "Timeout connecting to HLSS backend"
        except httpx.RequestError as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    async def get_instance_status(
        self,
        hlss_type: HLSSType,
        instance_id: str,
    ) -> Tuple[bool, Optional[HLSSStatusResponse], Optional[str]]:
        """
        Get the status of an instance from its HLSS backend.

        Args:
            hlss_type: The HLSS type configuration.
            instance_id: The instance ID.

        Returns:
            Tuple of (success, status_response, error_message)
        """
        status_url = f"{hlss_type.base_url.rstrip('/')}/instances/{instance_id}/status"

        headers = {}
        if hlss_type.auth_token:
            headers["Authorization"] = f"Bearer {hlss_type.auth_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(status_url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return True, HLSSStatusResponse(**data), None
                else:
                    return False, None, f"HLSS returned status {response.status_code}"

        except httpx.TimeoutException:
            return False, None, "Timeout connecting to HLSS backend"
        except httpx.RequestError as e:
            return False, None, f"Connection error: {str(e)}"
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"

    async def get_frame_metadata(
        self,
        hlss_type: HLSSType,
        instance_id: str,
    ) -> Tuple[bool, Optional[HLSSFrameMetadata], Optional[str]]:
        """
        Get frame metadata from HLSS to check if there's a newer frame.

        Args:
            hlss_type: The HLSS type configuration.
            instance_id: The instance ID.

        Returns:
            Tuple of (success, frame_metadata, error_message)
        """
        frame_url = f"{hlss_type.base_url.rstrip('/')}/instances/{instance_id}/frame"

        headers = {}
        if hlss_type.auth_token:
            headers["Authorization"] = f"Bearer {hlss_type.auth_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(frame_url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return True, HLSSFrameMetadata(**data), None
                elif response.status_code == 404:
                    return (
                        True,
                        HLSSFrameMetadata(instance_id=instance_id, has_frame=False),
                        None,
                    )
                else:
                    return False, None, f"HLSS returned status {response.status_code}"

        except httpx.TimeoutException:
            return False, None, "Timeout connecting to HLSS backend"
        except httpx.RequestError as e:
            return False, None, f"Connection error: {str(e)}"
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"

    async def request_frame_send(
        self,
        hlss_type: HLSSType,
        instance_id: str,
    ) -> Tuple[bool, Optional[HLSSFrameSendResponse], Optional[str]]:
        """
        Request HLSS to send (or re-send) the current frame.

        Args:
            hlss_type: The HLSS type configuration.
            instance_id: The instance ID.

        Returns:
            Tuple of (success, send_response, error_message)
        """
        send_url = (
            f"{hlss_type.base_url.rstrip('/')}/instances/{instance_id}/frame/send"
        )

        headers = {"Content-Type": "application/json"}
        if hlss_type.auth_token:
            headers["Authorization"] = f"Bearer {hlss_type.auth_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(send_url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return True, HLSSFrameSendResponse(**data), None
                elif response.status_code == 404:
                    return False, None, "Instance not found on HLSS"
                else:
                    return False, None, f"HLSS returned status {response.status_code}"

        except httpx.TimeoutException:
            return False, None, "Timeout connecting to HLSS backend"
        except httpx.RequestError as e:
            return False, None, f"Connection error: {str(e)}"
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"

    async def forward_input(
        self,
        hlss_type: HLSSType,
        instance_id: str,
        event: InputEvent,
    ) -> Tuple[bool, Optional[str]]:
        """
        Forward an input event to an HLSS instance.

        Args:
            hlss_type: The HLSS type configuration.
            instance_id: The instance ID.
            event: The input event.

        Returns:
            Tuple of (success, error_message)
        """
        input_url = f"{hlss_type.base_url.rstrip('/')}/instances/{instance_id}/inputs"

        headers = {"Content-Type": "application/json"}
        if hlss_type.auth_token:
            headers["Authorization"] = f"Bearer {hlss_type.auth_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    input_url,
                    json=event.model_dump(mode="json"),
                    headers=headers,
                )

                if response.status_code == 200:
                    return True, None
                else:
                    return False, f"HLSS returned status {response.status_code}"

        except httpx.TimeoutException:
            return False, "Timeout connecting to HLSS backend"
        except httpx.RequestError as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    async def trigger_render(
        self,
        hlss_type: HLSSType,
        instance_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Trigger a render for an HLSS instance.

        Args:
            hlss_type: The HLSS type configuration.
            instance_id: The instance ID.

        Returns:
            Tuple of (success, error_message)
        """
        render_url = f"{hlss_type.base_url.rstrip('/')}/instances/{instance_id}/render"

        headers = {}
        if hlss_type.auth_token:
            headers["Authorization"] = f"Bearer {hlss_type.auth_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(render_url, headers=headers)

                if response.status_code in (200, 202):
                    return True, None
                else:
                    return False, f"HLSS returned status {response.status_code}"

        except httpx.TimeoutException:
            return False, "Timeout connecting to HLSS backend"
        except httpx.RequestError as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"


async def initialize_hlss_instance(
    db: Session,
    instance: Instance,
    hlss_type: HLSSType,
    llss_base_url: str,
) -> Tuple[bool, Optional[str]]:
    """
    Initialize an HLSS instance and update database state.

    Args:
        db: Database session.
        instance: The instance to initialize.
        hlss_type: The HLSS type configuration.
        llss_base_url: Base URL of this LLSS instance.

    Returns:
        Tuple of (success, error_message)
    """
    # Determine display capabilities
    display = DisplayCapabilities(
        width=instance.display_width or hlss_type.default_width or 800,
        height=instance.display_height or hlss_type.default_height or 480,
        bit_depth=instance.display_bit_depth or hlss_type.default_bit_depth or 4,
        partial_refresh=False,
    )

    service = HLSSService(llss_base_url)
    success, config_url, error = await service.initialize_instance(
        hlss_type=hlss_type,
        instance=instance,
        display=display,
    )

    if success:
        instance.hlss_initialized = True
        instance.initialized_at = datetime.now(timezone.utc)
        instance.needs_configuration = config_url is not None
        instance.configuration_url = config_url
        instance.hlss_ready = not instance.needs_configuration
        instance.display_width = display.width
        instance.display_height = display.height
        instance.display_bit_depth = display.bit_depth
        db.commit()
        return True, None
    else:
        return False, error


async def refresh_hlss_status(
    db: Session,
    instance: Instance,
    hlss_type: HLSSType,
    llss_base_url: str,
) -> Tuple[bool, Optional[str]]:
    """
    Refresh the status of an HLSS instance from its backend.

    Args:
        db: Database session.
        instance: The instance to check.
        hlss_type: The HLSS type configuration.
        llss_base_url: Base URL of this LLSS instance.

    Returns:
        Tuple of (success, error_message)
    """
    service = HLSSService(llss_base_url)
    success, status, error = await service.get_instance_status(
        hlss_type=hlss_type,
        instance_id=instance.instance_id,
    )

    if success and status:
        instance.hlss_ready = status.ready
        instance.needs_configuration = status.needs_configuration
        instance.configuration_url = status.configuration_url
        db.commit()
        return True, None
    else:
        return False, error
